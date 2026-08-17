
from __future__ import annotations
import numpy as np
import pandas as pd

from .arima import prepare_series as prepare_arima_series, fit_arima, chronological_backtest
from .lstm import train_validation, prepare_series as prepare_lstm_series
from .metrics import mae, rmse, mape

def build_evaluation_frame(rows):
    return pd.DataFrame([
        {"sale_date":r.sale_date,"quantity":r.quantity}
        for r in rows
    ])

def evaluate_models(rows, horizon=30):
    if not rows:
        raise ValueError("No sales history exists for this product.")

    df=build_evaluation_frame(rows)
    arima_series=prepare_arima_series(df)
    lstm_series=prepare_lstm_series(df)

    # ARIMA: order selection on training history, then chronological holdout.
    arima_model, arima_info=fit_arima(arima_series)
    arima_validation=chronological_backtest(arima_series,arima_info["order"])

    # LSTM: its own chronological validation procedure.
    lstm_validation=train_validation(lstm_series,lookback=14,epochs=25)

    results=[
        {
            "model":"ARIMA",
            "mae":float(arima_validation["mae"]),
            "rmse":float(arima_validation["rmse"]),
            "mape":float(arima_validation["mape"]),
            "validation_days":int(arima_validation["validation_days"]),
            "details":{
                "order":list(arima_info["order"]),
                "d":int(arima_info["d"]),
                "aic":float(arima_info["aic"]),
                "bic":float(arima_info["bic"])
            }
        },
        {
            "model":"LSTM",
            "mae":float(lstm_validation["metrics"]["mae"]),
            "rmse":float(lstm_validation["metrics"]["rmse"]),
            "mape":float(lstm_validation["metrics"]["mape"]),
            "validation_days":int(lstm_validation["validation"]["validation_days"]),
            "details":{
                "lookback":int(lstm_validation["lookback"]),
                "epochs_ran":int(lstm_validation["history"]["epochs_ran"])
            }
        }
    ]

    def rank_key(x):
        # MAPE is the primary selection metric, with RMSE and MAE as tie-breakers.
        return (x["mape"],x["rmse"],x["mae"])

    ranked=sorted(results,key=rank_key)
    for i,r in enumerate(ranked,1):
        r["rank"]=i

    winner=ranked[0]["model"]

    # Comparison is descriptive, not a new model.
    return {
        "validation_protocol":"chronological holdout; no random shuffling",
        "primary_metric":"MAPE",
        "secondary_metrics":["RMSE","MAE"],
        "winner":winner,
        "models":ranked,
        "recommendation":(
            f"{winner} has the lowest validation MAPE for this product. "
            "Use the model comparison result as evidence, not as a guarantee of future accuracy."
        )
    }
