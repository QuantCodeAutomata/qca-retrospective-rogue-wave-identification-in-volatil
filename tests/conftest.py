import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_series():
    np.random.seed(42)
    N = 200
    t = np.linspace(0, 10 * np.pi, N)
    x = 20 + 5 * np.sin(t) + 3 * np.sin(3 * t) + np.random.normal(0, 0.5, N)
    dates = pd.date_range('2000-01-01', periods=N, freq='B')
    return pd.Series(x, index=dates)


@pytest.fixture
def synthetic_envelope():
    np.random.seed(42)
    N = 200
    t = np.linspace(0, 10 * np.pi, N)
    env = np.abs(20 + 5 * np.sin(t) + 3 * np.sin(3 * t))
    return env
