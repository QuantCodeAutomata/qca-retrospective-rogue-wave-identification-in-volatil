"""Finite-difference Schrödinger diagnostics (paper equations 2--5)."""
import numpy as np
import pandas as pd
from scipy.integrate import trapezoid
from scipy.linalg import eigh
from scipy.stats import skew as scipy_skew, kurtosis as scipy_kurtosis


_COLUMNS = ['date', 'lambda_min', 'abs_lambda_min', 'width', 'loc_distance',
            'skewness', 'kurtosis']


def _finite_vector(x, name):
    if np.iscomplexobj(x):
        raise ValueError(f'{name} must be real-valued')
    a = np.asarray(x, dtype=float)
    if a.ndim != 1 or not np.all(np.isfinite(a)):
        raise ValueError(f'{name} must be a finite one-dimensional array')
    return a


def _spacing(delta_t):
    if not np.isfinite(delta_t) or delta_t <= 0:
        raise ValueError('delta_t must be finite and strictly positive')
    return float(delta_t)


def build_operator(
    U_window: np.ndarray,
    boundary_condition: str = 'dirichlet',
    delta_t: float = 1.0,
) -> np.ndarray:
    """H = -1/2 D2 + diag(U), with an explicit boundary convention.

    ``dirichlet`` fixes the two observed window endpoints to zero and solves
    on the L-2 interior samples (the original repository convention).
    ``dirichlet_ghost`` fixes zero values just outside the observed interval,
    retaining all L observations. The paper does not state its boundary
    conditions; this alternative supports sensitivity checks. In particular,
    endpoint Dirichlet does not use the newest sample's potential in H.
    """
    u = _finite_vector(U_window, 'U_window')
    dt = _spacing(delta_t)
    if boundary_condition == 'dirichlet':
        if len(u) < 3:
            raise ValueError('Endpoint Dirichlet requires at least 3 samples')
        potential = u[1:-1]
    elif boundary_condition == 'dirichlet_ghost':
        if len(u) < 1:
            raise ValueError('Ghost Dirichlet requires at least 1 sample')
        potential = u
    else:
        raise ValueError("boundary_condition must be 'dirichlet' or 'dirichlet_ghost'")
    h = np.diag(1.0 / dt**2 + potential)
    if len(potential) > 1:
        off = np.full(len(potential) - 1, -0.5 / dt**2)
        h += np.diag(off, 1) + np.diag(off, -1)
    return h


def solve_min_eigenpair(H: np.ndarray) -> tuple:
    """Smallest eigenpair; Euclidean unit norm and positive largest component."""
    h = np.asarray(H, dtype=float)
    if (h.ndim != 2 or h.shape[0] != h.shape[1] or h.shape[0] == 0
            or not np.all(np.isfinite(h))):
        raise ValueError('H must be a finite nonempty square matrix')
    if not np.allclose(h, h.T, rtol=1e-12, atol=1e-12):
        raise ValueError('H must be symmetric')
    values, vectors = eigh(h, subset_by_index=[0, 0])
    v = vectors[:, 0]
    v = v / np.linalg.norm(v)
    if v[np.argmax(np.abs(v))] < 0:
        v = -v
    return float(values[0]), v


def compute_width(v: np.ndarray, delta_t: float = 1.0) -> float:
    """Equation 5, trapezoidal second moment about argmax(abs(v)).

    The integration domain consists of the supplied samples. Include known
    zero endpoints when passing an interior Dirichlet eigenvector, as done
    by rolling_schrodinger_analysis. Works for real or complex vectors.
    """
    a = np.asarray(v)
    dt = _spacing(delta_t)
    if a.ndim != 1 or len(a) == 0 or not np.all(np.isfinite(a)):
        raise ValueError('v must be a finite nonempty vector')
    magnitude = np.abs(a)
    scale = magnitude.max()
    if scale == 0:
        raise ValueError('width is undefined for a zero eigenvector')
    if len(a) == 1:
        return 0.0
    probability = (magnitude / scale) ** 2
    positions = np.arange(len(a), dtype=float) * dt
    origin = positions[np.argmax(magnitude)]
    return float(np.sqrt(trapezoid(probability * (positions - origin)**2, dx=dt)
                         / trapezoid(probability, dx=dt)))


def compute_localization_distance(
    v: np.ndarray, window_L: int, delta_t: float = 1.0,
) -> float:
    """Distance from the eigenvector maximum to the last observed sample.

    An L-2 vector occupies indices 1..L-2 of the original window, so its
    last interior sample is one trading day from the actual window end.
    A full L vector (ghost Dirichlet) occupies indices 0..L-1.
    """
    a = np.asarray(v)
    dt = _spacing(delta_t)
    if (a.ndim != 1 or not len(a) or not np.all(np.isfinite(a))
            or not np.any(np.abs(a))):
        raise ValueError('v must be a finite nonzero vector')
    if len(a) == window_L - 2:
        offset = 1
    elif len(a) == window_L:
        offset = 0
    else:
        raise ValueError('eigenvector length must be window_L or window_L - 2')
    return float((window_L - 1 - offset - np.argmax(np.abs(a))) * dt)


def compute_potential_moments(
    U: np.ndarray, bias: bool = False, fisher: bool = True,
) -> tuple:
    """Sample skewness and excess kurtosis; undefined for constant potentials.

    The manuscript does not specify bias correction or Fisher/Pearson
    convention; the original bias=False, fisher=True choices are retained.
    """
    u = _finite_vector(U, 'U')
    if len(u) < 2 or np.ptp(u) == 0:
        return float('nan'), float('nan')
    return float(scipy_skew(u, bias=bias)), float(scipy_kurtosis(u, fisher=fisher, bias=bias))


def rolling_schrodinger_analysis(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    window_L: int = 80,
    boundary_condition: str = 'dirichlet',
    delta_t: float = 1.0,
) -> pd.DataFrame:
    """Rolling retrospective diagnostics, with errors surfaced to the caller."""
    a = _finite_vector(envelope, 'envelope')
    dt = _spacing(delta_t)
    if isinstance(window_L, (bool, np.bool_)) or not isinstance(window_L, (int, np.integer)) or window_L < 3:
        raise ValueError('window_L must be an integer >= 3')
    if len(dates) != len(a):
        raise ValueError('dates and envelope must have equal length')
    if boundary_condition not in {'dirichlet', 'dirichlet_ghost'}:
        raise ValueError('unsupported boundary_condition')
    if np.any(a < 0):
        raise ValueError('envelope must be nonnegative')
    records = []
    for t in range(window_L - 1, len(a)):
        u = -a[t-window_L+1:t+1] ** 2
        h = build_operator(u, boundary_condition, dt)
        lam, v = solve_min_eigenpair(h)
        # Include the two known zero boundary values in the quadrature.
        width_vector = np.pad(v, 1) if boundary_condition == 'dirichlet' else v
        width = compute_width(width_vector, dt)
        distance = compute_localization_distance(v, window_L, dt)
        sk, kurt = compute_potential_moments(u)
        records.append(dict(date=dates[t], lambda_min=lam, abs_lambda_min=abs(lam),
                            width=width, loc_distance=distance, skewness=sk, kurtosis=kurt))
    return pd.DataFrame.from_records(records, columns=_COLUMNS)
