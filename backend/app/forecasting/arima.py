
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from sklearn.metrics import mean_squared_error, mean_absolute_error

from .metrics import mae, rmse, mape

warnings.filterwarnings("ignore")

def prepare_series(df: pd.DataFrame) -> pd.Series:
    s = df.copy()
    s["sale_date"] = pd.to_datetime(s["sale_date"], errors="coerce")
    s["quantity"] = pd.to_numeric(s["quantity"], errors="coerce")
    s = s.dropna(subset=["sale_date", "quantity"])
    s = s.groupby("sale_date")["quantity"].sum().sort_index()

    if len(s) < 21:
        raise ValueError("At least 21 historical daily observations are required.")

    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full, fill_value=0.0).astype(float)

def adf_test(series: pd.Series):
    values = np.asarray(series, dtype=float)
    if len(values) < 10 or np.std(values) < 1e-12:
        return {
            "statistic": None,
            "p_value": None,
            "lags": 0,
            "observations": len(values),
            "stationary": False,
            "reason": "ADF test is not reliable for a constant or very short series."
        }

    result = adfuller(values, autolag="AIC")
    return {
        "statistic": float(result[0]),
        "p_value": float(result[1]),
        "lags": int(result[2]),
        "observations": int(result[3]),
        "stationary": bool(result[1] < 0.05),
        "reason": "p-value < 0.05" if result[1] < 0.05 else "p-value >= 0.05"
    }

def choose_d(series: pd.Series, max_d: int = 2):
    current = series.copy()
    tests = []
    for d in range(max_d + 1):
        test = adf_test(current)
        test["d"] = d
        tests.append(test)
        if test["stationary"]:
            return d, tests
        current = current.diff().dropna()
    return max_d, tests

def select_order(series: pd.Series, d: int):
    """
    Small transparent grid search. AIC selects the order; validation later
    measures out-of-sample forecast quality.
    """
    candidates = []
    max_p = min(3, max(1, len(series)//40))
    max_q = min(3, max(1, len(series)//40))

    for p in range(max_p + 1):
        for q in range(max_q + 1):
            if p == 0 and q == 0:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fitted = ARIMA(series, order=(p, d, q)).fit()
                candidates.append({
                    "order": (p, d, q),
                    "aic": float(fitted.aic),
                    "bic": float(fitted.bic)
                })
            except Exception:
                continue

    if not candidates:
        return (1, d, 1), []

    candidates.sort(key=lambda x: x["aic"])
    return candidates[0]["order"], candidates[:10]

def fit_arima(series: pd.Series):
    d, adf_history = choose_d(series)
    order, candidates = select_order(series, d)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(series, order=order).fit()

    return model, {
        "order": order,
        "d": d,
        "adf": adf_history,
        "candidates": candidates,
        "aic": float(model.aic),
        "bic": float(model.bic)
    }

def chronological_backtest(series: pd.Series, order, validation_days=None):
    n = len(series)
    validation_days = validation_days or max(14, min(30, n//5))
    if n - validation_days < 15:
        raise ValueError("Insufficient history for ARIMA validation.")

    train = series.iloc[:-validation_days]
    test = series.iloc[-validation_days:]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ARIMA(train, order=order).fit()
        pred = np.asarray(fitted.forecast(validation_days), dtype=float)

    pred = np.maximum(pred, 0)
    actual = np.asarray(test, dtype=float)

    return {
        "validation_days": validation_days,
        "train_start": train.index.min().strftime("%Y-%m-%d"),
        "train_end": train.index.max().strftime("%Y-%m-%d"),
        "test_start": test.index.min().strftime("%Y-%m-%d"),
        "test_end": test.index.max().strftime("%Y-%m-%d"),
        "mae": mae(actual, pred),
        "rmse": rmse(actual, pred),
        "mape": mape(actual, pred),
        "actual": actual.tolist(),
        "predicted": pred.tolist(),
    }

def forecast_arima(series: pd.Series, horizon=30):
    model, info = fit_arima(series)
    forecast = model.get_forecast(steps=horizon)
    mean = np.asarray(forecast.predicted_mean, dtype=float)
    ci = forecast.conf_int(alpha=0.05)

    lower = np.asarray(ci.iloc[:, 0], dtype=float)
    upper = np.asarray(ci.iloc[:, 1], dtype=float)

    mean = np.maximum(mean, 0)
    lower = np.maximum(lower, 0)
    upper = np.maximum(upper, 0)

    return mean, lower, upper, info

def run_arima_pipeline(series: pd.Series, horizon=30):
    model, info = fit_arima(series)
    validation = chronological_backtest(series, info["order"])

    forecast = model.get_forecast(steps=horizon)
    mean = np.maximum(np.asarray(forecast.predicted_mean, dtype=float), 0)
    ci = forecast.conf_int(alpha=0.05)
    lower = np.maximum(np.asarray(ci.iloc[:,0], dtype=float), 0)
    upper = np.maximum(np.asarray(ci.iloc[:,1], dtype=float), 0)

    future_dates = pd.date_range(
        series.index.max() + pd.Timedelta(days=1),
        periods=horizon,
        freq="D"
    )

    return {
        "model": "ARIMA",
        "order": list(info["order"]),
        "d": info["d"],
        "aic": info["aic"],
        "bic": info["bic"],
        "adf": info["adf"],
        "order_candidates": [
            {"order": list(x["order"]), "aic": x["aic"], "bic": x["bic"]}
            for x in info["candidates"]
        ],
        "validation": {
            k:v for k,v in validation.items()
            if k not in ("actual","predicted")
        },
        "metrics": {
            "mae": validation["mae"],
            "rmse": validation["rmse"],
            "mape": validation["mape"]
        },
        "forecast": [
            {
                "date": d.strftime("%Y-%m-%d"),
                "value": float(mean[i]),
                "lower_95": float(lower[i]),
                "upper_95": float(upper[i])
            }
            for i,d in enumerate(future_dates)
        ]
    }

# Backward-compatible helpers used by earlier phases.
def backtest_arima(series):
    d, _ = choose_d(series)
    order, _ = select_order(series, d)
    result = chronological_backtest(series, order)
    return {"mae": result["mae"], "rmse": result["rmse"], "mape": result["mape"], "order": order}

def forecast_arima_legacy(series, horizon=30):
    values, _, _, info = forecast_arima(series, horizon)
    return values, info["order"]
