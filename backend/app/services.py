from datetime import datetime, timedelta
import json
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import Product, Sale, Forecast, ForecastValue, Alert, AuditLog
from .forecasting.arima import prepare_series as arima_series, backtest_arima, forecast_arima
from .forecasting.lstm import prepare_series as lstm_series, backtest_lstm, forecast_lstm

def product_sales_df(db, product_id, tenant_id=None, store_id=None):
    q = db.query(Sale).filter(Sale.product_id == product_id)
    if tenant_id is not None: q = q.filter(Sale.tenant_id == tenant_id)
    if store_id is not None: q = q.filter(Sale.store_id == store_id)
    rows = q.order_by(Sale.sale_date).all()
    if not rows:
        raise ValueError("No sales history exists for this product.")
    return pd.DataFrame([{"sale_date": r.sale_date, "quantity": r.quantity} for r in rows])

def generate_forecast(db: Session, product_id: int, horizon: int, tenant_id=None, store_id=None):
    qprod = db.query(Product).filter(Product.id == product_id)
    if tenant_id is not None: qprod = qprod.filter(Product.tenant_id == tenant_id)
    if store_id is not None: qprod = qprod.filter(Product.store_id == store_id)
    product = qprod.first()
    if not product:
        raise ValueError("Product not found.")

    df = product_sales_df(db, product_id, tenant_id, store_id)
    ar_series = arima_series(df)
    ar_metrics = backtest_arima(ar_series)
    ar_pred, order = forecast_arima(ar_series, horizon)

    lstm_metrics = None
    lstm_pred = None
    try:
        ls = lstm_series(df)
        lstm_metrics = backtest_lstm(ls)
        lstm_pred = forecast_lstm(ls, horizon)
    except Exception as exc:
        lstm_metrics = {"unavailable": str(exc)}

    candidates = [("ARIMA", ar_metrics, ar_pred)]
    if lstm_pred is not None and "mape" in lstm_metrics:
        candidates.append(("LSTM", lstm_metrics, lstm_pred))
    selected = min(candidates, key=lambda x: x[1]["mape"])

    forecast = Forecast(
        tenant_id=tenant_id if tenant_id is not None else product.tenant_id,
        store_id=store_id if store_id is not None else product.store_id,
        product_id=product_id,
        model=selected[0],
        horizon=horizon,
        mae=selected[1]["mae"],
        rmse=selected[1]["rmse"],
        mape=selected[1]["mape"],
        training_start=ar_series.index.min().to_pydatetime(),
        training_end=ar_series.index.max().to_pydatetime(),
    )
    db.add(forecast)
    db.flush()

    start = ar_series.index.max() + pd.Timedelta(days=1)
    for i, value in enumerate(selected[2], start=1):
        db.add(ForecastValue(
            forecast_id=forecast.id,
            forecast_date=(start + pd.Timedelta(days=i-1)).to_pydatetime(),
            value=float(value)
        ))

    db.add(AuditLog(action="FORECAST_GENERATED", details=json.dumps({
        "product_id": product_id, "model": selected[0], "horizon": horizon
    })))
    db.commit()

    return {
        "forecast_id": forecast.id,
        "product": product.name,
        "selected_model": selected[0],
        "metrics": {"mae": forecast.mae, "rmse": forecast.rmse, "mape": forecast.mape},
        "arima": {"metrics": ar_metrics, "forecast": ar_pred.tolist()},
        "lstm": {"metrics": lstm_metrics, "forecast": None if lstm_pred is None else lstm_pred.tolist()},
        "forecast": selected[2].tolist(),
        "dates": [(start + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(horizon)]
    }

def restock_for_product(db, product_id, tenant_id=None, store_id=None, horizon=30):
    qprod = db.query(Product).filter(Product.id==product_id)
    if tenant_id is not None: qprod=qprod.filter(Product.tenant_id==tenant_id)
    if store_id is not None: qprod=qprod.filter(Product.store_id==store_id)
    product=qprod.first()
    if not product: raise ValueError("Product not found.")
    qf = db.query(Forecast).filter(Forecast.product_id==product_id)
    if tenant_id is not None: qf=qf.filter(Forecast.tenant_id==tenant_id)
    if store_id is not None: qf=qf.filter(Forecast.store_id==store_id)
    latest = qf.order_by(Forecast.created_at.desc()).first()
    if not latest:
        result = generate_forecast(db, product_id, horizon, tenant_id, store_id)
        latest = db.query(Forecast).get(result["forecast_id"])
    values = db.query(ForecastValue).filter(ForecastValue.forecast_id==latest.id).all()
    daily = sum(v.value for v in values) / max(len(values),1)
    lead_demand = daily * product.lead_time_days
    target = lead_demand + product.safety_stock
    order_qty = max(0, target - product.current_stock)
    level = "CRITICAL" if order_qty > product.current_stock else ("ATTENTION" if order_qty > 0 else "HEALTHY")
    return {
        "product_id": product.id, "product": product.name, "current_stock": product.current_stock,
        "forecast_demand": sum(v.value for v in values),
        "safety_stock": product.safety_stock, "lead_time_demand": lead_demand,
        "recommended_order": round(order_qty,2), "priority": level,
        "model": latest.model, "mape": latest.mape,
        "reason": f"{'Forecasted lead-time demand exceeds available stock.' if order_qty > 0 else 'Available stock covers configured lead-time demand.'}"
    }
