import numpy as np

def mae(actual, pred):
    a, p = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    return float(np.mean(np.abs(a - p)))

def rmse(actual, pred):
    a, p = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    return float(np.sqrt(np.mean((a - p) ** 2)))

def mape(actual, pred):
    a, p = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    mask = np.abs(a) > 1e-9
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)
