
from __future__ import annotations
import os
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL","2")

import numpy as np
import pandas as pd

from .metrics import mae, rmse, mape

def _tf():
    import tensorflow as tf
    return tf

def prepare_series(df: pd.DataFrame) -> pd.Series:
    s=df.copy()
    s["sale_date"]=pd.to_datetime(s["sale_date"],errors="coerce")
    s["quantity"]=pd.to_numeric(s["quantity"],errors="coerce")
    s=s.dropna(subset=["sale_date","quantity"])
    s=s.groupby("sale_date")["quantity"].sum().sort_index()
    if len(s)<45:
        raise ValueError("At least 45 historical daily observations are required for LSTM.")
    full=pd.date_range(s.index.min(),s.index.max(),freq="D")
    return s.reindex(full,fill_value=0.0).astype(float)

def make_sequences(values, lookback):
    X=[];y=[]
    for i in range(lookback,len(values)):
        X.append(values[i-lookback:i])
        y.append(values[i])
    return np.asarray(X,dtype=np.float32),np.asarray(y,dtype=np.float32)

def _build_model(lookback):
    tf=_tf()
    model=tf.keras.Sequential([
        tf.keras.layers.Input(shape=(lookback,1)),
        tf.keras.layers.LSTM(48),
        tf.keras.layers.Dropout(0.15),
        tf.keras.layers.Dense(24,activation="relu"),
        tf.keras.layers.Dense(1)
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),loss="mse")
    return model

def train_validation(series,lookback=14,epochs=25):
    tf=_tf()
    from sklearn.preprocessing import MinMaxScaler

    values=np.asarray(series,dtype=float).reshape(-1,1)
    scaler=MinMaxScaler()
    scaled=scaler.fit_transform(values).flatten()
    X,y=make_sequences(scaled,lookback)

    if len(X)<30:
        raise ValueError("Insufficient sequences for LSTM validation.")

    split=max(10,int(len(X)*0.8))
    if len(X)-split<5:
        raise ValueError("Insufficient validation observations for LSTM.")

    X_train=X[:split].reshape(-1,lookback,1)
    y_train=y[:split]
    X_test=X[split:].reshape(-1,lookback,1)
    y_test=y[split:]

    model=_build_model(lookback)
    callback=tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",patience=5,restore_best_weights=True
    )
    history=model.fit(
        X_train,y_train,
        validation_split=0.15,
        epochs=epochs,
        batch_size=16,
        verbose=0,
        callbacks=[callback]
    )

    pred_scaled=model.predict(X_test,verbose=0).flatten()
    actual=scaler.inverse_transform(y_test.reshape(-1,1)).flatten()
    pred=scaler.inverse_transform(pred_scaled.reshape(-1,1)).flatten()
    pred=np.maximum(pred,0)

    return {
        "model":model,
        "scaler":scaler,
        "lookback":lookback,
        "metrics":{
            "mae":mae(actual,pred),
            "rmse":rmse(actual,pred),
            "mape":mape(actual,pred)
        },
        "validation":{
            "validation_days":len(actual),
            "test_start":series.index[-len(actual)].strftime("%Y-%m-%d"),
            "test_end":series.index[-1].strftime("%Y-%m-%d")
        },
        "history":{
            "epochs_ran":len(history.history.get("loss",[])),
            "final_loss":float(history.history["loss"][-1]),
            "final_val_loss":float(history.history["val_loss"][-1])
        }
    }

def fit_full(series,lookback=14,epochs=25):
    from sklearn.preprocessing import MinMaxScaler
    values=np.asarray(series,dtype=float).reshape(-1,1)
    scaler=MinMaxScaler()
    scaled=scaler.fit_transform(values).flatten()
    X,y=make_sequences(scaled,lookback)
    if len(X)<20:
        raise ValueError("Insufficient history for LSTM training.")
    model=_build_model(lookback)
    callback=_tf().keras.callbacks.EarlyStopping(
        monitor="loss",patience=5,restore_best_weights=True
    )
    history=model.fit(
        X.reshape(-1,lookback,1),y,
        epochs=epochs,batch_size=16,verbose=0,callbacks=[callback]
    )
    return model,scaler,history

def recursive_forecast(model,scaler,series,horizon,lookback):
    scaled=scaler.transform(np.asarray(series,dtype=float).reshape(-1,1)).flatten()
    window=list(scaled[-lookback:])
    preds=[]
    for _ in range(horizon):
        x=np.asarray(window[-lookback:],dtype=np.float32).reshape(1,lookback,1)
        value=float(model.predict(x,verbose=0)[0,0])
        preds.append(value)
        window.append(value)
    result=scaler.inverse_transform(np.asarray(preds).reshape(-1,1)).flatten()
    return np.maximum(result,0)

def run_lstm_pipeline(series: pd.Series,horizon=30,lookback=14,epochs=25):
    validation=train_validation(series,lookback,epochs)
    model,scaler,history=fit_full(series,lookback,epochs)
    future=recursive_forecast(model,scaler,series,horizon,lookback)
    dates=pd.date_range(series.index.max()+pd.Timedelta(days=1),periods=horizon,freq="D")
    return {
        "model":"LSTM",
        "lookback":lookback,
        "epochs_requested":epochs,
        "validation":validation["validation"],
        "metrics":validation["metrics"],
        "training":{
            "epochs_ran":len(history.history.get("loss",[])),
            "final_loss":float(history.history["loss"][-1])
        },
        "forecast":[
            {"date":d.strftime("%Y-%m-%d"),"value":float(future[i])}
            for i,d in enumerate(dates)
        ]
    }

def backtest_lstm(series,lookback=14,epochs=15):
    x=train_validation(series,lookback,epochs)
    return x["metrics"]

# Backward-compatible forecast helper.
def forecast_lstm(series,horizon=30,lookback=14,epochs=25):
    model,scaler,_=fit_full(series,lookback,epochs)
    return recursive_forecast(model,scaler,series,horizon,lookback)
