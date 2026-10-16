import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.stats import skew as scipy_skew, kurtosis as scipy_kurtosis


def build_operator(
    U_window: np.ndarray,
    boundary_condition: str = 'dirichlet',
    delta_t: float = 1.0
) -> np.ndarray:
    """Build (L-2)x(L-2) interior Schrodinger Hamiltonian with Dirichlet BC.
    Eigenvalue problem: lambda*v = -1/2 * d2v/dt2 + U*v
    FD: H[k,k] = 1/dt^2 + U[k], H[k,k+1] = H[k-1,k] = -1/(2*dt^2)
    With dt=1: H[k,k] = 1+U[k], off-diag = -0.5
    Interior indices: 1..L-2 (L = window length)
    """
    L = len(U_window)
    if L < 3:
        raise ValueError(f'Window too short for Dirichlet BC: L={L}, need L>=3')
    dt2 = delta_t ** 2
    interior = U_window[1:L-1]  # L-2 interior points
    M = len(interior)
    H = np.zeros((M, M))
    np.fill_diagonal(H, 1.0 / dt2 + interior)
    off = -0.5 / dt2
    for i in range(M - 1):
        H[i, i+1] = off
        H[i+1, i] = off
    return H


def solve_min_eigenpair(H: np.ndarray) -> tuple:
    """Solve for minimum eigenvalue using scipy.linalg.eigh.
    Returns (lambda_min, v_min) normalized; sign: max |v| component > 0.
    """
    eigenvalues, eigenvectors = eigh(H)
    idx = np.argmin(eigenvalues)
    lam = float(eigenvalues[idx])
    v = eigenvectors[:, idx].copy()
    # normalize
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    # sign convention: max |v| component positive
    max_idx = np.argmax(np.abs(v))
    if v[max_idx] < 0:
        v = -v
    return lam, v


def compute_width(v: np.ndarray) -> float:
    """Width via second moment: w = sqrt(sum(|v|^2*(k-k0)^2) / sum(|v|^2)).
    k0 = argmax(|v|). Uses np.trapz for numerical integration.
    """
    v2 = v ** 2
    k0 = float(np.argmax(np.abs(v)))
    k = np.arange(len(v), dtype=float)
    numerator = np.trapz(v2 * (k - k0) ** 2)
    denominator = np.trapz(v2)
    if denominator <= 0:
        return 0.0
    return float(np.sqrt(numerator / denominator))


def compute_localization_distance(v: np.ndarray, window_L: int) -> float:
    """Distance of peak |v| from end of window.
    v has length (L-2) for interior Dirichlet; interior end index = L-3.
    distance = (L-3) - argmax(|v|)
    """
    end_interior = window_L - 3
    peak_pos = int(np.argmax(np.abs(v)))
    return float(max(0, end_interior - peak_pos))


def compute_potential_moments(
    U: np.ndarray,
    bias: bool = False,
    fisher: bool = True
) -> tuple:
    """Compute (skewness, kurtosis) of potential U. bias=False, fisher=True (excess)."""
    sk = float(scipy_skew(U, bias=bias))
    kurt = float(scipy_kurtosis(U, fisher=fisher, bias=bias))
    return sk, kurt


def rolling_schrodinger_analysis(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    window_L: int = 80,
    boundary_condition: str = 'dirichlet'
) -> pd.DataFrame:
    """Rolling window Schrodinger analysis. Returns DataFrame with:
    date, lambda_min, abs_lambda_min, width, loc_distance, skewness, kurtosis
    """
    N = len(envelope)
    records = []
    for t in range(window_L - 1, N):
        window = envelope[t - window_L + 1: t + 1]
        U = -window ** 2
        try:
            H = build_operator(U, boundary_condition=boundary_condition)
            lam, v = solve_min_eigenpair(H)
            w = compute_width(v)
            d = compute_localization_distance(v, window_L)
            sk, kurt = compute_potential_moments(U)
        except Exception:
            lam, v, w, d, sk, kurt = np.nan, None, np.nan, np.nan, np.nan, np.nan
        records.append({
            'date': dates[t],
            'lambda_min': lam,
            'abs_lambda_min': abs(lam) if not np.isnan(lam) else np.nan,
            'width': w,
            'loc_distance': d,
            'skewness': sk,
            'kurtosis': kurt,
        })
    return pd.DataFrame(records)
