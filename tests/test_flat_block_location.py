import numpy as np
import pytest
from src.realtime_pipeline import compute_warning_indicator


@pytest.mark.parametrize("scale", [1.0, 1000.0, 10000.0])
def test_flat_block_location_stable_under_roundoff(scale):
    block = np.full(10, scale)
    perturbed = block.copy()
    perturbed[-1] = np.nextafter(scale, np.inf)
    for values in (block, perturbed):
        m, c, w, offset = compute_warning_indicator(values)
        assert offset == 0
        assert m == np.gradient(values).max()
        assert c == 0 and w == 0


def test_resolvable_small_gradient_keeps_actual_location():
    block = np.full(10, 1000.0)
    block[-1] += 1e-6
    assert compute_warning_indicator(block)[3] == 9


def test_active_gradient_not_canonicalized_at_large_scale():
    block = np.full(10, 1e16)
    block[-1] += 100
    m, c, w, offset = compute_warning_indicator(block)
    assert m == 100 and c == 1 and w == 100 and offset == 9
