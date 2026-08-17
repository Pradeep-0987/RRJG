# RetailPulse AI — Project QA Report

## Scope
Static/in-repository QA performed across the current backend, frontend, database scripts, routes, dataset and project configuration.

## Checks completed
- Python syntax compilation: PASS
- Backend route registration audit: PASS (33 route decorators found)
- Frontend-to-backend API path audit: PASS for all concrete frontend calls; `/forecast/` is a dynamic prefix covered by `/forecast/studio` and `/forecast` routes.
- Demo dataset schema: PASS
- Demo dataset completeness: PASS (8,772 rows, 12 products, 6 columns, no nulls)
- PostgreSQL configuration: PASS (`postgresql+psycopg` URL in `.env.example`)
- Enterprise Product schema migration: PASS — automatic startup migration added
- Seed reset robustness: PASS — PostgreSQL schema reset uses `DROP SCHEMA public CASCADE` in the development seed
- Dataset import verification: PASS — frontend now verifies product/sales counts after import
- Sidebar scrolling: PASS — dedicated scroll container added to fixed sidebar
- Dataset drag/drop UI: PASS
- Settings route defensive loading/error handling: PASS
- React error boundary: PASS

## Environment limitation
A production browser build could not be executed in this isolated environment because the frontend dependency tree was not installed and package installation timed out without network access. The project should therefore be validated locally with `npm install && npm run build` before deployment.

## Important production note
`backend/.env` contains environment-specific secrets and should not be committed or shared. Use `.env.example` as the template and rotate any demo secret before production.

## Recommended acceptance test
1. Start PostgreSQL.
2. Start FastAPI on port 8000.
3. Confirm `/api/v1/health`.
4. Login as OWNER.
5. Open Data Intelligence.
6. Upload `retailpulse_demo_2year.csv`.
7. Click Import & Replace and confirm.
8. Verify the UI reports products and sales counts from PostgreSQL.
9. Open Products and confirm imported products.
10. Open Reports and test daily/weekly/monthly/yearly.
11. Open Forecast Studio, ARIMA, LSTM and Model Evaluation.
12. Open Inventory, Restock Center, Scenario Planner and Copilot.
13. Scroll the sidebar all the way down and open Settings & Access.
14. Run `npm run build` before release.
