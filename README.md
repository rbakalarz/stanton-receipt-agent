# Stanton Receipt Agent

Automatically detects every charge on Visa Corporativa **4183 (GNB Sudameris),
finds the matching receipt email, generates a PDF, and files it in Google Drive.
Sends a weekly digest to accounting with matched receipts and any missing ones.

## How it works

```
Nightly (2am Bogotá)
  ↓
1. Scan inbox for new Sudameris notifications from Notificaciones@gnbsudameris.com.co
2. Parse: vendor, amount (COP), date
3. Search for matching receipt email (±3 days)
4. Convert receipt to PDF
5. Upload to Google Drive → Recibos Stanton / YYYY-MM / VENDOR_DATE_AMOUNT.pdf
6. Log to Supabase (matched or missing_receipt)
7. Apply Gmail label (receipt-processed or receipt-missing)
8. Every Monday: send digest email to accounting
```

## Setup

### 1. Supabase
Run `scripts/schema.sql` in your Supabase SQL editor.

### 2. Google Drive
- Create a folder called **"Recibos Stanton"** in Google Drive
- Create a Google Cloud project → enable Drive API
- Create a **Service Account** → download JSON key
- Share the "Recibos Stanton" folder with the service account email (Editor access)
- Note the folder ID from the Drive URL

### 3. Gmail OAuth
Use the same OAuth credentials from your existing Claude integration.
Export the token JSON as `GMAIL_CREDENTIALS_JSON`.

### 4. Environment variables (set in Railway)

```
GMAIL_CREDENTIALS_JSON          # Full token.json content (JSON string)
GOOGLE_SERVICE_ACCOUNT_JSON     # Service account key (JSON string)
DRIVE_ROOT_FOLDER_ID            # ID of the "Recibos Stanton" Drive folder
SUPABASE_URL                    # Your Supabase project URL
SUPABASE_SERVICE_ROLE_KEY       # Supabase service role key
WKHTMLTOPDF_PATH                # /usr/bin/wkhtmltopdf (default, already in Docker)

# Weekly report email
REPORT_EMAIL_TO                 # e.g. contabilidad@stanton.co
REPORT_EMAIL_FROM               # r@stanton.co
SMTP_HOST                       # smtp.gmail.com
SMTP_PORT                       # 587
SMTP_USER                       # r@stanton.co
SMTP_PASS                       # Gmail app password (not your regular password)
```

### 5. Deploy to Railway
```bash
railway login
railway init
railway up
```

The `railway.toml` sets the cron to run daily at 2am Bogotá (7am UTC).

## Adding new vendors

If a vendor isn't being matched automatically, add it to `VENDOR_SENDER_MAP`
in `src/gmail_client.py`:

```python
"NUEVO PROVEEDOR": ["sender@dominio.com"],
```

## Manual receipt upload

For physical receipts (Rappi, etc.), scan and email to r@stanton.co
with the vendor name in the subject — the agent will pick it up on the next run.

## Google Drive structure

```
Recibos Stanton/
  2025-03/
    CANVA_2025-03-15_COP57420.pdf
    GRAMMARLY_2025-03-01_COP113160.pdf
    ...
  2025-04/
    ...
  2026-03/
    ANTHROPIC_2026-03-18_COP188287.pdf
    LOVABLE_2026-03-17_COP187962.pdf
    ...
```

## Supabase queries

```sql
-- All charges this month
select vendor, txn_date, amount_cop, status
from receipts
where txn_date >= date_trunc('month', current_date)
order by txn_date;

-- Missing receipts
select * from missing_receipts;

-- Monthly totals
select * from receipts_monthly_summary;
```
