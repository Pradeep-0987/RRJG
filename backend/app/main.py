
from datetime import datetime
from pathlib import Path
import json
import pandas as pd
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, inspect, text
from .db import Base, engine, get_db
from .models import Tenant, Store, User, Product, Sale, Forecast, ForecastValue, Alert, AuditLog
from .schemas import LoginRequest, ForecastRequest, ScenarioRequest, CopilotRequest
from .auth import hash_password, verify_password, create_token, require_auth, require_roles, ROLES
from .services import generate_forecast, restock_for_product
from .data_quality.pipeline import normalize_columns, detect_columns, score_quality, clean_dataframe, forecast_readiness
from .inventory.service import inventory_dashboard, inventory_position, update_stock
from .inventory.advisor import advise, restock_center
from .scenarios.service import get_product as get_scenario_product, calculate_scenario, scenario_compare
from .dashboard.service import dashboard_data
from .alerts.service import build_alerts
from .reports.service import report_summary
from .forecasting.arima import run_arima_pipeline, prepare_series as arima_prepare_series
from .forecasting.lstm import run_lstm_pipeline, prepare_series as lstm_prepare_series
from .forecasting.evaluation import evaluate_models
from .seasonality.analysis import prepare_daily, seasonality_report, anomaly_report


PRODUCT_MIGRATION_COLUMNS = {
    "company": "VARCHAR(160) DEFAULT 'RetailPulse Demo'",
    "brand": "VARCHAR(160) DEFAULT ''",
    "subcategory": "VARCHAR(160) DEFAULT ''",
    "unit_price": "DOUBLE PRECISION DEFAULT 0",
    "unit_cost": "DOUBLE PRECISION DEFAULT 0",
    "currency": "VARCHAR(8) DEFAULT 'INR'",
    "barcode": "VARCHAR(80) DEFAULT ''",
    "supplier": "VARCHAR(160) DEFAULT ''",
}

def ensure_enterprise_schema():
    """Create missing tables/columns so an older RetailPulse DB can be upgraded in place."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "products" not in inspector.get_table_names():
            Base.metadata.create_all(bind=conn)
            inspector = inspect(conn)
        columns = {c["name"] for c in inspector.get_columns("products")}
        for name, ddl in PRODUCT_MIGRATION_COLUMNS.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {ddl}"))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS ix_products_tenant_store_company ON products (tenant_id, store_id, company)",
            "CREATE INDEX IF NOT EXISTS ix_products_tenant_store_brand ON products (tenant_id, store_id, brand)",
            "CREATE INDEX IF NOT EXISTS ix_sales_tenant_store_date ON sales (tenant_id, store_id, sale_date)",
        ):
            conn.execute(text(stmt))

ensure_enterprise_schema()

app = FastAPI(title="RetailPulse AI API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def scoped_products(db, user):
    return db.query(Product).filter(
        Product.tenant_id == user["tenant_id"],
        Product.store_id == user["store_id"]
    )

def scoped_sales(db, user):
    return db.query(Sale).filter(
        Sale.tenant_id == user["tenant_id"],
        Sale.store_id == user["store_id"]
    )

@app.get("/health")
@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status":"healthy","database":"connected","forecast_engine":"ARIMA + LSTM","phase":"enterprise"}

@app.get("/api/v1/system/diagnostics")
def system_diagnostics(db: Session = Depends(get_db), user=Depends(require_auth)):
    """Safe, tenant-scoped health information used by the Data Intelligence UI."""
    product_count = scoped_products(db, user).count()
    sales_count = scoped_sales(db, user).count()
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("products")} if "products" in inspector.get_table_names() else set()
    required = {"company","brand","subcategory","unit_price","unit_cost","currency","barcode","supplier"}
    return {
        "database": "postgresql" if engine.dialect.name == "postgresql" else engine.dialect.name,
        "schema_ready": required.issubset(columns),
        "products": product_count,
        "sales": sales_count,
        "tables": sorted(inspector.get_table_names()),
    }

@app.post("/api/v1/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email==req.email).first()
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {
        "access_token": create_token(user),
        "role": user.role,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "store_id": user.store_id
    }

@app.get("/api/v1/auth/me")
def me(user=Depends(require_auth), db:Session=Depends(get_db)):
    u=db.query(User).filter(User.id==user["user_id"], User.tenant_id==user["tenant_id"]).first()
    if not u: raise HTTPException(404,"User not found")
    tenant=db.query(Tenant).get(u.tenant_id)
    store=db.query(Store).get(u.store_id) if u.store_id else None
    return {
        "id":u.id,"email":u.email,"role":u.role,
        "tenant":{"id":tenant.id,"name":tenant.name,"slug":tenant.slug},
        "store":None if not store else {"id":store.id,"name":store.name,"location":store.location}
    }

@app.get("/api/v1/auth/permissions")
def permissions(user=Depends(require_auth)):
    role=user["role"]
    matrix={
        "OWNER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot","settings","users"],
        "MANAGER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot"],
        "STAFF":["dashboard","products","inventory","restock","alerts"],
        "ANALYST":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","reports","copilot"],
        "CUSTOMER":["products","availability","copilot"]
    }
    return {"role":role,"permissions":matrix[role]}


@app.get("/api/v1/settings/overview")
def settings_overview(db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    tenant=db.query(Tenant).filter(Tenant.id==user["tenant_id"]).first()
    stores=db.query(Store).filter(Store.tenant_id==user["tenant_id"]).all()
    users=db.query(User).filter(User.tenant_id==user["tenant_id"]).all()
    return {
        "tenant":{"id":tenant.id,"name":tenant.name,"slug":tenant.slug},
        "stores":[{"id":s.id,"name":s.name,"location":s.location} for s in stores],
        "users":[{"id":u.id,"email":u.email,"role":u.role,"store_id":u.store_id,"active":u.is_active} for u in users],
        "roles":sorted(ROLES),
        "permission_matrix":{
            "OWNER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot","settings","users"],
            "MANAGER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot"],
            "STAFF":["dashboard","products","inventory","restock","alerts"],
            "ANALYST":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","reports","copilot"],
            "CUSTOMER":["products","availability","copilot"]
        }
    }

@app.get("/api/v1/tenant")
def tenant_info(user=Depends(require_auth), db:Session=Depends(get_db)):
    t=db.query(Tenant).filter(Tenant.id==user["tenant_id"]).first()
    stores=db.query(Store).filter(Store.tenant_id==t.id).all()
    return {"id":t.id,"name":t.name,"slug":t.slug,
            "stores":[{"id":s.id,"name":s.name,"location":s.location} for s in stores]}

@app.get("/api/v1/users")
def users(db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    rows=db.query(User).filter(User.tenant_id==user["tenant_id"]).all()
    return [{"id":u.id,"email":u.email,"role":u.role,"store_id":u.store_id,"active":u.is_active} for u in rows]

@app.post("/api/v1/users")
def create_user(payload:dict, db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    email=str(payload.get("email","")).strip().lower()
    role=str(payload.get("role","STAFF")).upper()
    password=str(payload.get("password",""))
    store_id=payload.get("store_id")
    if not email or len(password)<8 or role not in ROLES:
        raise HTTPException(400,"Email, password (8+ characters) and valid role are required")
    if db.query(User).filter(User.email==email).first():
        raise HTTPException(409,"User already exists")
    if store_id is not None and not db.query(Store).filter(Store.id==store_id,Store.tenant_id==user["tenant_id"]).first():
        raise HTTPException(400,"Store does not belong to this tenant")
    u=User(tenant_id=user["tenant_id"],store_id=store_id,email=email,password_hash=hash_password(password),role=role)
    db.add(u)
    db.add(AuditLog(tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],action="USER_CREATED",details=json.dumps({"email":email,"role":role})))
    db.commit()
    return {"id":u.id,"email":u.email,"role":u.role,"store_id":u.store_id}

@app.get("/api/v1/reports/summary")
def reports_summary(days:int=30, db:Session=Depends(get_db),
                    user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    try:
        return report_summary(
            db,
            user["tenant_id"],
            user["store_id"],
            days
        )
    except ValueError as e:
        raise HTTPException(400, str(e))



@app.get("/api/v1/reports/periodic")
def periodic_report(period: str = "daily", db: Session = Depends(get_db),
                    user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    """Chart-ready daily/weekly/monthly/yearly reports anchored to the uploaded dataset."""
    period = period.lower().strip()
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        raise HTTPException(400, "period must be daily, weekly, monthly or yearly")

    rows = scoped_sales(db, user).order_by(Sale.sale_date).all()
    if not rows:
        return {
            "period": period,
            "anchor_date": None,
            "kpis": {"total_units": 0, "average_units": 0, "peak_units": 0,
                     "growth_pct": None, "records": 0},
            "series": [],
            "top_products": []
        }

    df = pd.DataFrame([
        {"date": r.sale_date, "quantity": float(r.quantity), "product_id": r.product_id}
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return {
            "period": period, "anchor_date": None,
            "kpis": {"total_units": 0, "average_units": 0, "peak_units": 0,
                     "growth_pct": None, "records": 0},
            "series": [], "top_products": []
        }

    anchor = pd.Timestamp(df["date"].max()).normalize()

    if period == "daily":
        start = anchor - pd.Timedelta(days=29)
        bucketed = df.assign(bucket=df["date"].dt.normalize())
        expected = pd.date_range(start, anchor, freq="D")
        grouped = bucketed.groupby("bucket")["quantity"].sum()
        series = [
            {"label": d.strftime("%Y-%m-%d"),
             "units": round(float(grouped.get(d, 0)), 2)}
            for d in expected
        ]
    elif period == "weekly":
        start = anchor - pd.Timedelta(weeks=11)
        iso = df["date"].dt.isocalendar()
        df["bucket"] = [
            f"{int(y)}-W{int(w):02d}" for y, w in zip(iso.year, iso.week)
        ]
        grouped = df.groupby("bucket")["quantity"].sum()
        start_week = start.to_period("W-SUN").start_time
        series = []
        for i in range(12):
            d = start_week + pd.Timedelta(weeks=i)
            iso_year = int(d.isocalendar().year)
            iso_week = int(d.isocalendar().week)
            key = f"{iso_year}-W{iso_week:02d}"
            series.append({"label": key, "units": round(float(grouped.get(key, 0)), 2)})
    elif period == "monthly":
        start = anchor.to_period("M") - 11
        df["bucket"] = df["date"].dt.to_period("M").astype(str)
        grouped = df.groupby("bucket")["quantity"].sum()
        months = pd.period_range(start=start, end=anchor.to_period("M"), freq="M")
        series = [
            {"label": str(m), "units": round(float(grouped.get(str(m), 0)), 2)}
            for m in months
        ]
    else:
        start_year = anchor.year - 4
        df["bucket"] = df["date"].dt.year.astype(str)
        grouped = df.groupby("bucket")["quantity"].sum()
        series = [
            {"label": str(y), "units": round(float(grouped.get(str(y), 0)), 2)}
            for y in range(start_year, anchor.year + 1)
        ]

    values = [float(x["units"]) for x in series]
    total = sum(values)
    avg = total / len(values) if values else 0
    peak = max(values) if values else 0

    # Compare the last half of the report periods with the first half.
    growth = None
    if len(values) >= 4:
        half = len(values) // 2
        old = sum(values[:half]) / max(half, 1)
        new = sum(values[half:]) / max(len(values) - half, 1)
        if old:
            growth = round((new - old) / old * 100, 2)

    product_ids = df.groupby("product_id")["quantity"].sum().sort_values(ascending=False).head(10)
    product_rows = []
    for pid, units in product_ids.items():
        p = db.query(Product).filter(Product.id == int(pid)).first()
        product_rows.append({
            "product": p.name if p else f"Product {pid}",
            "units": round(float(units), 2)
        })

    return {
        "period": period,
        "anchor_date": anchor.strftime("%Y-%m-%d"),
        "kpis": {
            "total_units": round(total, 2),
            "average_units": round(avg, 2),
            "peak_units": round(peak, 2),
            "growth_pct": growth,
            "records": int(len(df))
        },
        "series": series,
        "top_products": product_rows
    }

@app.get("/api/v1/alerts")
def alerts(db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    return build_alerts(db,user["tenant_id"],user["store_id"])

@app.get("/api/v1/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","STAFF","ANALYST"))):
    return dashboard_data(db, user["tenant_id"], user["store_id"])

@app.get("/api/v1/products")
def products(db: Session=Depends(get_db), user=Depends(require_auth)):
    return scoped_products(db,user).order_by(Product.name).all()

@app.get("/api/v1/products/{product_id}")
def product(product_id:int, db:Session=Depends(get_db), user=Depends(require_auth)):
    p=scoped_products(db,user).filter(Product.id==product_id).first()
    if not p: raise HTTPException(404,"Product not found")
    inv=inventory_position(db,product_id,user["tenant_id"],user["store_id"])
    return {
        "id":p.id,"sku":p.sku,"name":p.name,"company":p.company,"brand":p.brand,
        "category":p.category,"subcategory":p.subcategory,"unit_price":p.unit_price,
        "unit_cost":p.unit_cost,"currency":p.currency,"barcode":p.barcode,"supplier":p.supplier,
        "current_stock":p.current_stock,"lead_time_days":p.lead_time_days,
        "safety_stock":p.safety_stock,"inventory":inv
    }

@app.post("/api/v1/products")
def create_product(payload:dict, db:Session=Depends(get_db),
                   user=Depends(require_roles("OWNER","MANAGER"))):
    sku=str(payload.get("sku","")).strip()
    name=str(payload.get("name","")).strip()
    category=str(payload.get("category","General")).strip()
    if not sku or not name: raise HTTPException(400,"SKU and product name are required")
    if scoped_products(db,user).filter(Product.sku==sku).first():
        raise HTTPException(409,"SKU already exists in this store")
    p=Product(
        tenant_id=user["tenant_id"],store_id=user["store_id"],sku=sku,name=name,
        company=str(payload.get("company","RetailPulse Demo")),
        brand=str(payload.get("brand","")),category=category,
        subcategory=str(payload.get("subcategory","")),
        unit_price=float(payload.get("unit_price",0)),unit_cost=float(payload.get("unit_cost",0)),
        currency=str(payload.get("currency","INR")),barcode=str(payload.get("barcode","")),
        supplier=str(payload.get("supplier","")),
        current_stock=float(payload.get("current_stock",0)),
        lead_time_days=int(payload.get("lead_time_days",7)),
        safety_stock=float(payload.get("safety_stock",10))
    )
    if p.current_stock<0 or p.lead_time_days<0 or p.safety_stock<0:
        raise HTTPException(400,"Stock, lead time and safety stock cannot be negative")
    db.add(p); db.commit(); db.refresh(p)
    return p

@app.patch("/api/v1/products/{product_id}")
def update_product(product_id:int,payload:dict,db:Session=Depends(get_db),
                   user=Depends(require_roles("OWNER","MANAGER"))):
    p=scoped_products(db, user).filter(Product.id==product_id).first()
    if not p: raise HTTPException(404,"Product not found")
    for field in ["sku","name","company","brand","category","subcategory","currency","barcode","supplier"]:
        if field in payload and str(payload[field]).strip():
            setattr(p,field,str(payload[field]).strip())
    for field in ["current_stock","safety_stock","unit_price","unit_cost"]:
        if field in payload:
            value=float(payload[field])
            if value<0: raise HTTPException(400,f"{field} cannot be negative")
            setattr(p,field,value)
    if "lead_time_days" in payload:
        value=int(payload["lead_time_days"])
        if value<0: raise HTTPException(400,"lead_time_days cannot be negative")
        p.lead_time_days=value
    db.commit();db.refresh(p)
    return p

@app.get("/api/v1/inventory")
def inventory(db:Session=Depends(get_db),user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    return inventory_dashboard(db,user["tenant_id"],user["store_id"])

@app.get("/api/v1/inventory/{product_id}")
def inventory_product(product_id:int,db:Session=Depends(get_db),user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    x=inventory_position(db,product_id,user["tenant_id"],user["store_id"])
    if not x: raise HTTPException(404,"Product not found")
    return x

@app.patch("/api/v1/inventory/{product_id}/stock")
def change_stock(product_id:int,payload:dict,db:Session=Depends(get_db),
                 user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    if "stock" not in payload: raise HTTPException(400,"stock is required")
    try: x=update_stock(db,product_id,user["tenant_id"],user["store_id"],float(payload["stock"]))
    except ValueError as e: raise HTTPException(400,str(e))
    if not x: raise HTTPException(404,"Product not found")
    return x

@app.post("/api/v1/data/reset")
def reset_dataset(db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    """Delete the current store's products and all dependent retail/model data.

    Tenant/store scoped and intentionally OWNER-only because this is destructive.
    Audit history is preserved.
    """
    tenant_id=user["tenant_id"]
    store_id=user["store_id"]
    if store_id is None:
        raise HTTPException(400,"No store is assigned to this account.")

    product_ids=[x[0] for x in db.query(Product.id).filter(
        Product.tenant_id==tenant_id, Product.store_id==store_id
    ).all()]

    forecast_ids=[x[0] for x in db.query(Forecast.id).filter(
        Forecast.tenant_id==tenant_id, Forecast.store_id==store_id
    ).all()]
    if forecast_ids:
        db.query(ForecastValue).filter(ForecastValue.forecast_id.in_(forecast_ids)).delete(synchronize_session=False)
    db.query(Forecast).filter(
        Forecast.tenant_id==tenant_id, Forecast.store_id==store_id
    ).delete(synchronize_session=False)
    db.query(Sale).filter(
        Sale.tenant_id==tenant_id, Sale.store_id==store_id
    ).delete(synchronize_session=False)
    db.query(Alert).filter(
        Alert.tenant_id==tenant_id, Alert.store_id==store_id
    ).delete(synchronize_session=False)
    deleted=db.query(Product).filter(
        Product.tenant_id==tenant_id, Product.store_id==store_id
    ).delete(synchronize_session=False)

    db.add(AuditLog(
        tenant_id=tenant_id, store_id=store_id, user_id=user["user_id"],
        action="DATASET_RESET",
        details=json.dumps({"products_deleted":deleted})
    ))
    db.commit()
    return {"status":"success","products_deleted":int(deleted),
            "message":"Current store dataset was cleared. You can now upload a new dataset."}

@app.post("/api/v1/data/upload")
async def upload(file: UploadFile=File(...), db:Session=Depends(get_db),
                 user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if not file.filename.lower().endswith((".csv",".xlsx",".xls")):
        raise HTTPException(400,"Only CSV and Excel files are supported.")
    data=await file.read()
    temp=Path("data_upload.tmp")
    temp.write_bytes(data)
    try:
        df=pd.read_csv(temp) if file.filename.lower().endswith(".csv") else pd.read_excel(temp)
    except Exception:
        raise HTTPException(400,"The uploaded file could not be read.")
    finally:
        temp.unlink(missing_ok=True)

    if df.empty:
        raise HTTPException(400,"The uploaded file contains no records.")

    df=normalize_columns(df)
    mapping,confidence=detect_columns(df)
    quality=score_quality(df,mapping)
    cleaned,duplicates_removed=clean_dataframe(df,mapping)
    readiness=forecast_readiness(cleaned,mapping)

    if not mapping.get("date") or not mapping.get("product") or not mapping.get("quantity"):
        return {
            "status":"needs_mapping",
            "filename":file.filename,
            "rows":len(df),
            "columns":list(df.columns),
            "mapping":mapping,
            "confidence":confidence,
            "quality":quality,
            "cleaned_rows":len(cleaned),
            "duplicates_removed":duplicates_removed,
            "readiness":readiness
        }

    inserted=0
    for name,group in cleaned.groupby("_product"):
        name=str(name)
        p=scoped_products(db,user).filter(Product.name==name).first()
        if not p:
            category="Imported"
            if mapping.get("category") and len(group):
                category=str(group.iloc[0][mapping["category"]])
            p=Product(
                tenant_id=user["tenant_id"],store_id=user["store_id"],
                sku=f"SKU-{abs(hash(name))%100000}",name=name,category=category
            )
            db.add(p); db.flush()

        for _,row in group.iterrows():
            db.add(Sale(
                tenant_id=user["tenant_id"],store_id=user["store_id"],product_id=p.id,
                sale_date=pd.Timestamp(row["_date"]).to_pydatetime(),quantity=float(row["_quantity"])
            ))
            inserted+=1

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="DATA_UPLOADED",
        details=json.dumps({
            "filename":file.filename,"raw_rows":len(df),"clean_rows":len(cleaned),
            "records_inserted":inserted,"duplicates_removed":duplicates_removed,
            "quality_score":quality["score"]
        })
    ))
    db.commit()

    return {
        "status":"success",
        "filename":file.filename,
        "raw_rows":len(df),
        "cleaned_rows":len(cleaned),
        "records_inserted":inserted,
        "products_detected":int(cleaned["_product"].nunique()),
        "mapping":mapping,
        "confidence":confidence,
        "quality":quality,
        "duplicates_removed":duplicates_removed,
        "readiness":readiness
    }

@app.post("/api/v1/data/replace")
async def replace_dataset(file: UploadFile=File(...), db:Session=Depends(get_db),
                          user=Depends(require_roles("OWNER"))):
    """Validate/analyze a dataset first, then atomically replace the store data."""
    if not file.filename or not file.filename.lower().endswith((".csv",".xlsx",".xls")):
        raise HTTPException(400,"Only CSV and Excel files are supported.")

    data=await file.read()
    if len(data)>25*1024*1024:
        raise HTTPException(400,"Dataset is too large. Maximum size is 25 MB.")
    temp=Path("data_replace.tmp")
    temp.write_bytes(data)
    try:
        df=pd.read_csv(temp) if file.filename.lower().endswith(".csv") else pd.read_excel(temp)
    except Exception:
        raise HTTPException(400,"The uploaded dataset could not be read.")
    finally:
        temp.unlink(missing_ok=True)

    if df.empty:
        raise HTTPException(400,"The uploaded dataset contains no records.")

    df=normalize_columns(df)
    mapping,confidence=detect_columns(df)
    quality=score_quality(df,mapping)
    cleaned,duplicates_removed=clean_dataframe(df,mapping)
    readiness=forecast_readiness(cleaned,mapping)

    required=(mapping.get("date"),mapping.get("product"),mapping.get("quantity"))
    if not all(required):
        return {
            "status":"needs_mapping", "filename":file.filename, "raw_rows":len(df),
            "columns":list(df.columns), "mapping":mapping, "confidence":confidence,
            "quality":quality, "cleaned_rows":len(cleaned),
            "duplicates_removed":duplicates_removed, "readiness":readiness,
            "message":"Dataset was analyzed but not imported because required columns were not detected."
        }
    if cleaned.empty:
        raise HTTPException(400,"No valid records remain after cleaning. Nothing was replaced.")

    tenant_id=user["tenant_id"]; store_id=user["store_id"]
    # Refuse unsafe writes if an older database schema is still in place.
    inspector=inspect(engine)
    product_columns={c["name"] for c in inspector.get_columns("products")}
    missing=sorted(set(PRODUCT_MIGRATION_COLUMNS)-product_columns)
    if missing:
        raise HTTPException(500, "Database schema is outdated. Restart the backend so the automatic migration can run, or execute scripts/migrate_enterprise_db.py. Missing columns: " + ", ".join(missing))
    # Clear dependent data only after validation has succeeded.
    forecast_ids=[x[0] for x in db.query(Forecast.id).filter(
        Forecast.tenant_id==tenant_id, Forecast.store_id==store_id
    ).all()]
    if forecast_ids:
        db.query(ForecastValue).filter(ForecastValue.forecast_id.in_(forecast_ids)).delete(synchronize_session=False)
    db.query(Forecast).filter(Forecast.tenant_id==tenant_id, Forecast.store_id==store_id).delete(synchronize_session=False)
    db.query(Sale).filter(Sale.tenant_id==tenant_id, Sale.store_id==store_id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.tenant_id==tenant_id, Alert.store_id==store_id).delete(synchronize_session=False)
    db.query(Product).filter(Product.tenant_id==tenant_id, Product.store_id==store_id).delete(synchronize_session=False)

    inserted=0
    product_count=0
    for name,group in cleaned.groupby("_product"):
        name=str(name).strip()
        category="Imported"
        if mapping.get("category") and len(group):
            val=group.iloc[0].get(mapping["category"])
            if pd.notna(val) and str(val).strip(): category=str(val).strip()

        sku=f"SKU-{abs(hash(name))%100000}"
        stock=0.0
        if mapping.get("inventory") and len(group):
            vals=pd.to_numeric(group[mapping["inventory"]],errors="coerce").dropna()
            if len(vals): stock=float(vals.iloc[-1])
        # Give imported products sensible operational defaults when the dataset
        # does not contain explicit planning parameters.
        daily_avg=float(pd.to_numeric(group["_quantity"],errors="coerce").mean() or 0)
        safety=max(10.0, round(daily_avg*2.0, 2))

        brand=""
        company="Imported Catalog"
        if mapping.get("brand") and len(group):
            v=group.iloc[0].get(mapping["brand"]); brand="" if pd.isna(v) else str(v).strip()
        if mapping.get("company") and len(group):
            v=group.iloc[0].get(mapping["company"]); company="Imported Catalog" if pd.isna(v) or not str(v).strip() else str(v).strip()
        p=Product(tenant_id=tenant_id,store_id=store_id,sku=sku,name=name,
                  company=company,brand=brand,category=category,current_stock=max(0,stock),
                  lead_time_days=7,safety_stock=safety)
        db.add(p); db.flush()
        product_count+=1
        for _,row in group.iterrows():
            db.add(Sale(tenant_id=tenant_id,store_id=store_id,product_id=p.id,
                        sale_date=pd.Timestamp(row["_date"]).to_pydatetime(),quantity=float(row["_quantity"])))
            inserted+=1

    # Produce actual dataset-level analysis for the UI.
    date_series=pd.to_datetime(cleaned["_date"],errors="coerce")
    quantities=pd.to_numeric(cleaned["_quantity"],errors="coerce")
    grouped=cleaned.groupby("_product")["_quantity"].sum().sort_values(ascending=False)
    analysis={
        "products":int(product_count),
        "sales_records":int(inserted),
        "total_units":round(float(quantities.sum()),2),
        "date_start":date_series.min().strftime("%Y-%m-%d"),
        "date_end":date_series.max().strftime("%Y-%m-%d"),
        "top_products":[{"product":str(k),"units":round(float(v),2)} for k,v in grouped.head(10).items()],
        "average_daily_units":round(float(grouped.sum()/max((date_series.max()-date_series.min()).days+1,1)),2),
        "forecast_ready_products":int(sum(
            (g["_date"].max()-g["_date"].min()).days>=45
            for _,g in cleaned.groupby("_product")
        ))
    }

    db.add(AuditLog(tenant_id=tenant_id,store_id=store_id,user_id=user["user_id"],
        action="DATASET_REPLACED",details=json.dumps({
            "filename":file.filename,"raw_rows":len(df),"clean_rows":len(cleaned),
            "products":product_count,"records_inserted":inserted,
            "duplicates_removed":duplicates_removed,"quality_score":quality["score"]
        })))
    db.commit()
    return {
        "status":"success", "mode":"replace", "filename":file.filename,
        "raw_rows":len(df), "cleaned_rows":len(cleaned),
        "records_inserted":inserted, "products_detected":product_count,
        "mapping":mapping,"confidence":confidence,"quality":quality,
        "duplicates_removed":duplicates_removed,"readiness":readiness,
        "analysis":analysis,
        "message":"Dataset analyzed and imported. Previous store products and dependent forecast/sales data were replaced."
    }

@app.post("/api/v1/evaluation/compare")
def compare_models(req:ForecastRequest, db:Session=Depends(get_db),
                   user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    product=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not product:
        raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==req.product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()

    try:
        result=evaluate_models(rows,req.horizon)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"Model evaluation failed: {e}")

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="MODEL_COMPARISON_RUN",
        details=json.dumps({
            "product_id":req.product_id,
            "winner":result["winner"],
            "primary_metric":result["primary_metric"]
        })
    ))
    db.commit()

    return {
        "product_id":product.id,
        "product":product.name,
        "sku":product.sku,
        **result
    }

@app.post("/api/v1/forecast/lstm")
def lstm_forecast_endpoint(req:ForecastRequest, db:Session=Depends(get_db),
                           user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if req.horizon<1 or req.horizon>365:
        raise HTTPException(400,"Horizon must be 1-365 days.")
    product=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not product: raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==req.product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()
    if not rows: raise HTTPException(400,"No sales history exists for this product.")

    df=pd.DataFrame([{"sale_date":r.sale_date,"quantity":r.quantity} for r in rows])
    try:
        series=lstm_prepare_series(df)
        result=run_lstm_pipeline(series,req.horizon)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"LSTM pipeline failed: {e}")

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="LSTM_PIPELINE_RUN",
        details=json.dumps({
            "product_id":req.product_id,
            "horizon":req.horizon,
            "lookback":result["lookback"],
            "mape":result["metrics"]["mape"]
        })
    ))
    db.commit()
    return {"product_id":product.id,"product":product.name,"sku":product.sku,**result}

@app.post("/api/v1/forecast/arima")
def arima_forecast_endpoint(req:ForecastRequest, db:Session=Depends(get_db),
                            user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if req.horizon < 1 or req.horizon > 365:
        raise HTTPException(400,"Horizon must be 1-365 days.")
    product=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not product:
        raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==req.product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()

    if not rows:
        raise HTTPException(400,"No sales history exists for this product.")

    df=pd.DataFrame([{"sale_date":r.sale_date,"quantity":r.quantity} for r in rows])
    try:
        series=arima_prepare_series(df)
        result=run_arima_pipeline(series,req.horizon)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"ARIMA pipeline failed: {e}")

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="ARIMA_PIPELINE_RUN",
        details=json.dumps({
            "product_id":req.product_id,
            "horizon":req.horizon,
            "order":result["order"],
            "mape":result["metrics"]["mape"]
        })
    ))
    db.commit()

    return {
        "product_id":product.id,
        "product":product.name,
        "sku":product.sku,
        **result
    }

@app.get("/api/v1/seasonality")
def seasonality(product_id:int, db:Session=Depends(get_db),
                user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    product=scoped_products(db,user).filter(Product.id==product_id).first()
    if not product: raise HTTPException(404,"Product not found.")
    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()
    try:
        series=prepare_daily(rows)
        report=seasonality_report(series)
    except ValueError as e: raise HTTPException(400,str(e))
    return {"product_id":product.id,"product":product.name,**report}

@app.get("/api/v1/anomalies")
def anomalies(product_id:int, db:Session=Depends(get_db),
              user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    product=scoped_products(db,user).filter(Product.id==product_id).first()
    if not product: raise HTTPException(404,"Product not found.")
    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()
    try:
        series=prepare_daily(rows)
        report=anomaly_report(series)
    except ValueError as e: raise HTTPException(400,str(e))
    return {"product_id":product.id,"product":product.name,**report}

@app.get("/api/v1/forecast/studio")
def forecast_studio(product_id:int, horizon:int=30, model:str="AUTO",
                     db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if horizon < 1 or horizon > 365:
        raise HTTPException(400,"Horizon must be 1-365 days.")

    product=scoped_products(db,user).filter(Product.id==product_id).first()
    if not product:
        raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()

    if not rows:
        raise HTTPException(400,"No sales history exists for this product.")

    df=pd.DataFrame([{"sale_date":r.sale_date,"quantity":r.quantity} for r in rows])

    # AUTO uses the model-comparison layer; explicit ARIMA/LSTM runs only that model.
    selected=model.upper()
    comparison=None
    if selected=="AUTO":
        try:
            comparison=evaluate_models(rows,horizon)
            selected=comparison["winner"]
        except Exception as e:
            raise HTTPException(400,f"Model selection failed: {e}")

    try:
        if selected=="ARIMA":
            series=arima_prepare_series(df)
            result=run_arima_pipeline(series,horizon)
        elif selected=="LSTM":
            series=lstm_prepare_series(df)
            result=run_lstm_pipeline(series,horizon)
        else:
            raise HTTPException(400,"model must be AUTO, ARIMA or LSTM")
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"Forecast Studio failed: {e}")

    history_start=pd.to_datetime(df["sale_date"]).min()
    history_end=pd.to_datetime(df["sale_date"]).max()
    daily=df.groupby(pd.to_datetime(df["sale_date"]).dt.normalize())["quantity"].sum().sort_index()
    history=[
        {"date":d.strftime("%Y-%m-%d"),"value":float(v)}
        for d,v in daily.tail(180).items()
    ]

    return {
        "product_id":product.id,
        "product":product.name,
        "sku":product.sku,
        "selected_model":selected,
        "selection_mode":model.upper(),
        "history_start":history_start.strftime("%Y-%m-%d"),
        "history_end":history_end.strftime("%Y-%m-%d"),
        "history":history,
        "forecast":result["forecast"],
        "metrics":result["metrics"],
        "model_details": {
            k:v for k,v in result.items()
            if k not in ("forecast","metrics")
        },
        "comparison":comparison
    }

@app.post("/api/v1/forecast")
def forecast(req:ForecastRequest, db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if req.horizon<1 or req.horizon>365: raise HTTPException(400,"Horizon must be 1-365 days.")
    if not scoped_products(db,user).filter(Product.id==req.product_id).first():
        raise HTTPException(404,"Product not found")
    try: return generate_forecast(db,req.product_id,req.horizon,user["tenant_id"],user["store_id"])
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception: raise HTTPException(500,"Forecast generation could not be completed.")

@app.get("/api/v1/inventory/advisor")
def inventory_advisor(product_id:int, db:Session=Depends(get_db),
                      user=Depends(require_roles("OWNER","MANAGER","STAFF","ANALYST"))):
    p=scoped_products(db,user).filter(Product.id==product_id).first()
    if not p: raise HTTPException(404,"Product not found.")
    return advise(db,p)

@app.get("/api/v1/restock/center")
def restock_center_api(db:Session=Depends(get_db),
                       user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    return restock_center(db,user["tenant_id"],user["store_id"])

@app.get("/api/v1/restock")
def restock(db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    out=[]
    for p in scoped_products(db,user).all():
        try: out.append(restock_for_product(db,p.id,user["tenant_id"],user["store_id"]))
        except Exception: pass
    return out

@app.post("/api/v1/scenarios")
def scenario(req:ScenarioRequest, db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    p=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not p: raise HTTPException(404,"Product not found")
    try:r=restock_for_product(db,p.id,user["tenant_id"],user["store_id"])
    except Exception as e:raise HTTPException(400,str(e))
    demand=r["forecast_demand"]*(1+req.demand_change_percent/100)
    stock=p.current_stock*(1+req.stock_change_percent/100)
    lead=req.lead_time_days if req.lead_time_days is not None else p.lead_time_days
    order=max(0,(demand/30)*lead+p.safety_stock-stock)
    return {"label":"SIMULATED SCENARIO","base":r,
            "scenario":{"forecast_demand":demand,"available_stock":stock,"lead_time_days":lead,"recommended_order":order}}

@app.post("/api/v1/copilot")
def copilot(req:CopilotRequest, db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST","CUSTOMER"))):
    """Grounded retail copilot. Uses only current store database facts; no invented numbers."""
    q=req.question.strip().lower()
    if not q:
        raise HTTPException(400,"Please enter a question.")
    products=scoped_products(db,user).all()
    if not products:
        return {"answer":"I cannot analyze the store yet because no products are loaded.","data":[],"sources":["products"],"action":"Open Data Intelligence and upload a CSV or Excel sales dataset."}
    product_map={p.id:p for p in products}
    sales=scoped_sales(db,user).all()
    total_units=sum(float(x.quantity or 0) for x in sales)
    sales_by={}
    for x in sales: sales_by[x.product_id]=sales_by.get(x.product_id,0)+float(x.quantity or 0)
    top_sales=sorted(sales_by.items(),key=lambda kv:kv[1],reverse=True)
    latest={}
    for f in db.query(Forecast).filter(Forecast.tenant_id==user["tenant_id"],Forecast.store_id==user["store_id"]).order_by(Forecast.created_at.desc()).all():
        latest.setdefault(f.product_id,f)
    forecast_info=[]
    for pid,f in latest.items():
        vals=db.query(ForecastValue).filter(ForecastValue.forecast_id==f.id).all()
        forecast_total=sum(max(0,float(v.value or 0)) for v in vals)
        forecast_info.append({"product":product_map[pid].name if pid in product_map else str(pid),"product_id":pid,"model":f.model,"mape":f.mape,"forecast_units":round(forecast_total,2)})
    forecast_info.sort(key=lambda x:x["forecast_units"],reverse=True)
    if user["role"]=="CUSTOMER":
        matches=[{"product":product_map[pid].name,"current_stock":product_map[pid].current_stock} for pid,_ in top_sales[:8]]
        return {"answer":"I can help with product availability. I do not expose internal forecasting or replenishment intelligence for customer accounts.","data":matches,"sources":["products","sales"],"action":"Ask about a product's availability."}
    if any(w in q for w in ["restock","reorder","order","run out","stock"]):
        ranked=[]
        for p in products:
            daily=sales_by.get(p.id,0)/max(len({x.sale_date.date() for x in sales if x.product_id==p.id}),1)
            cover=p.current_stock/daily if daily>0 else None
            need=max(0,daily*(p.lead_time_days+30)+p.safety_stock-p.current_stock)
            ranked.append({"product":p.name,"sku":p.sku,"current_stock":round(p.current_stock,2),"daily_demand":round(daily,2),"recommended_order":round(need,2),"days_cover":round(cover,2) if cover is not None else None})
        ranked.sort(key=lambda x:x["recommended_order"],reverse=True)
        return {"answer":"Based on current sales velocity, lead time and safety stock, these products have the highest replenishment need.","data":ranked[:8],"sources":["products","sales","inventory"],"action":"Open Restock Center to review the recommendations."}
    if any(w in q for w in ["mape","accuracy","model","arima","lstm","forecast"]):
        if not forecast_info:
            return {"answer":"No stored forecasts are available yet. Generate an ARIMA/LSTM forecast first.","data":[],"sources":["forecasts"],"action":"Open Forecast Studio."}
        return {"answer":f"I found {len(forecast_info)} stored product forecasts. The strongest forecast by projected demand is {forecast_info[0]['product']} using {forecast_info[0]['model']}, with MAPE {forecast_info[0]['mape']:.2f}% when a validation metric is available.","data":forecast_info[:8],"sources":["forecasts","forecast_values"],"action":"Open Model Evaluation for the full comparison."}
    if any(w in q for w in ["top","best selling","sales","sold","demand"]):
        data=[{"product":product_map[pid].name,"units":round(v,2)} for pid,v in top_sales[:8] if pid in product_map]
        return {"answer":f"The store has {total_units:,.0f} recorded sales units. These are the top products by recorded units.","data":data,"sources":["sales","products"],"action":"Open Reports for daily, weekly, monthly and yearly trends."}
    if any(w in q for w in ["risk","critical","low stock","danger"]):
        risks=[{"product":p.name,"stock":p.current_stock,"safety_stock":p.safety_stock,"risk":"CRITICAL" if p.current_stock<=p.safety_stock else "WATCH"} for p in products]
        risks.sort(key=lambda x:x["stock"]-x["safety_stock"])
        return {"answer":"These products are closest to or below their safety-stock threshold.","data":risks[:8],"sources":["products"],"action":"Open Action Center and Restock Center."}
    return {"answer":f"I can analyze {len(products)} products and {len(sales)} sales records in this store. Ask me about sales, demand, forecasts, ARIMA/LSTM accuracy, stock risk or restocking.","data":{"products":len(products),"sales_records":len(sales),"sales_units":round(total_units,2)},"sources":["products","sales","forecasts"],"action":"Try: Which products should I restock?"}

