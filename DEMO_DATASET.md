# RetailPulse AI Demo Dataset

File: `retailpulse_demo_2year.csv`

## Columns
- date
- product_id
- product_name
- category
- units_sold
- inventory

## Why it fits
- 12 products
- 731 days (2024-01-01 through 2025-12-31)
- 8,772 sales rows
- weekly seasonality
- yearly seasonality
- trend
- weekend uplift
- festive uplift
- inventory values

This is intentionally structured to match the RetailPulse AI data-quality aliases and to provide
more than enough history for ARIMA/LSTM readiness.
