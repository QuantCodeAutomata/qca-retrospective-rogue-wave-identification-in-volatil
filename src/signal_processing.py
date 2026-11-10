"""FFT/Hilbert envelope extraction with explicit paper-ambiguity choices."""
import numpy as np
from scipy.signal import find_peaks, hilbert


def _real_vector(x, name="signal"):
    if np.iscomplexobj(x):
        raise ValueError(f"{name} must be real-valued")
    a = np.asarray(x, dtype=float)
    if a.ndim != 1 or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be a finite one-dimensional array")
    return a


def mirror_series(x: np.ndarray) -> tuple:
    """Reflect without duplicated endpoints: x followed by x[-2:0:-1].

    The manuscript specifies mirroring, but not its endpoint convention.
    Returns the extended array and original length.
    """
    x = _real_vector(x)
    n = len(x)
    return (np.concatenate([x, x[-2:0:-1]]) if n > 1 else x.copy()), n


def spectral_peak_filter(
    x_mirrored: np.ndarray,
    percentile_threshold: float = 92.5,
    filter_mode: str = "spectral_peaks",
) -> np.ndarray:
    """Threshold real-FFT amplitudes using an explicitly selected population.

    ``spectral_peaks`` computes the percentile over interior local maxima of
    the one-sided amplitude spectrum, then removes every coefficient whose
    amplitude is below that threshold. DC and Nyquist are not local maxima
    in scipy.find_peaks and are not included in that percentile population;
    they are subjected to the same amplitude cutoff as the other bins.
    If no spectral maxima exist, no threshold can be estimated and the
    spectrum is returned unchanged.

    ``all_bins`` is the previous implementation: percentile over all rFFT
    amplitudes. It is retained for sensitivity analysis, not as evidence of
    the authors' exact algorithm. The manuscript does not specify whether
    non-peak bins should also be removed, treatment of DC/Nyquist, or the
    exact peak finder in Fourier space. Both choices are reproducible
    conventions; neither is selected by fitting reported performance.
    """
    x = _real_vector(x_mirrored)
    if not np.isfinite(percentile_threshold) or not 0 <= percentile_threshold <= 100:
        raise ValueError("percentile_threshold must be in [0, 100]")
    if filter_mode not in {"spectral_peaks", "all_bins"}:
        raise ValueError("filter_mode must be 'spectral_peaks' or 'all_bins'")
    if len(x) == 0:
        return np.array([], dtype=complex)
    spectrum = np.fft.rfft(x)
    amplitude = np.abs(spectrum)
    if filter_mode == "spectral_peaks":
        peaks, _ = find_peaks(amplitude)
        if not len(peaks):
            return spectrum
        population = amplitude[peaks]
    else:
        population = amplitude
    cutoff = np.percentile(population, percentile_threshold)
    return np.where(amplitude >= cutoff, spectrum, 0.0)


def reconstruct_filtered_signal(X_filtered: np.ndarray, n: int) -> np.ndarray:
    """Inverse real FFT; pass the original mirrored length as n."""
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError("n must be a positive integer")
    coefficients = np.asarray(X_filtered)
    if coefficients.ndim != 1 or not np.all(np.isfinite(coefficients)):
        raise ValueError("Fourier coefficients must be finite and one-dimensional")
    return np.fft.irfft(coefficients, n=n)


def extract_envelope(signal: np.ndarray) -> np.ndarray:
    """Absolute analytic signal; callers must supply the mirrored domain."""
    x = _real_vector(signal)
    if len(x) == 0:
        return x.copy()
    return np.abs(hilbert(x))


def process_series(
    x: np.ndarray,
    percentile_threshold: float = 92.5,
    filter_mode: str = "spectral_peaks",
) -> np.ndarray:
    """Mirror -> filter -> inverse FFT -> Hilbert -> crop original interval.

    Hilbert must operate on the mirrored domain too. Cropping beforehand
    reintroduces the nonperiodic endpoint jump which mirroring is meant to
    avoid. No undocumented amplitude normalisation is performed: output
    remains in the input index units.
    """
    mirrored, n = mirror_series(x)
    coefficients = spectral_peak_filter(mirrored, percentile_threshold, filter_mode)
    if n == 0:
        return np.array([], dtype=float)
    reconstructed = reconstruct_filtered_signal(coefficients, len(mirrored))
    return extract_envelope(reconstructed)[:n]
