# RetailPulse AI — PostgreSQL Enterprise Database

RetailPulse AI now supports PostgreSQL as the recommended production-style database.
SQLite remains available as a local fallback when `DATABASE_URL` is not set.

## 1. Start PostgreSQL

From the project root:

```powershell
docker compose up -d postgres
```

Verify:

```powershell
docker ps
```

You should see `retailpulse-postgres`.

## 2. Configure backend

The included `backend/.env` points to:

```text
postgresql+psycopg://retailpulse:retailpulse@localhost:5432/retailpulse
```

For a real deployment, replace the password and `SECRET_KEY`.

## 3. Install backend dependencies

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 4. Prepare / migrate schema

```powershell
python scripts/migrate_enterprise_db.py
```

This creates the tables and adds enterprise product-master fields when an older database already exists.

## 5. Seed the international demo catalog

```powershell
python scripts/seed_international_catalog.py
```

The demo contains representative products from major global brands across electronics, fashion, FMCG, beauty, home and appliances.

**The catalog is for demonstration only. RetailPulse AI is not affiliated with the listed brands.**

## 6. Start API

```powershell
uvicorn app.main:app --reload --port 8000
```

The application health indicator should show **PostgreSQL connected**.

## 7. Start frontend

```powershell
cd ..\frontend
npm install
npm run dev
```

## Data model

The core database contains:

- tenants
- stores
- users
- products
- sales
- forecasts
- forecast_values
- alerts
- audit_logs

Products now also contain:

- company
- brand
- category
- subcategory
- SKU
- barcode
- supplier
- unit price
- unit cost
- currency
- current stock
- safety stock
- lead time

This supports a more realistic enterprise product-master and inventory workflow.
