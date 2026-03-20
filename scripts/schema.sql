-- Stanton Receipt Agent — Supabase Schema
-- Run this once in your Supabase SQL editor

-- Receipts table: one row per Sudameris charge notification
create table if not exists receipts (
  id                uuid primary key default gen_random_uuid(),
  email_id          text not null,          -- Sudameris notification message ID
  vendor            text not null,          -- e.g. "ANTHROPIC", "UBER * EATS P"
  amount_cop        numeric(14,2) not null, -- charge amount in COP
  txn_date          date not null,          -- transaction date
  txn_datetime      timestamptz,            -- full timestamp from notification
  email_date        text,                   -- raw Date header from notification email
  status            text not null           -- 'matched' | 'missing_receipt' | 'skipped'
                    check (status in ('matched', 'missing_receipt', 'skipped')),
  receipt_email_id  text,                   -- Gmail message ID of the receipt email
  drive_url         text,                   -- Google Drive web view link
  filename          text,                   -- e.g. ANTHROPIC_2026-03-18_COP188287.pdf
  created_at        timestamptz default now()
);

-- Index for common queries
create index if not exists receipts_txn_date_idx   on receipts (txn_date desc);
create index if not exists receipts_vendor_idx      on receipts (vendor);
create index if not exists receipts_status_idx      on receipts (status);

-- Processed emails: prevents double-processing
create table if not exists processed_emails (
  email_id      text primary key,
  processed_at  timestamptz default now(),
  skipped       boolean default false
);

-- Useful views for accounting

-- Monthly summary
create or replace view receipts_monthly_summary as
select
  to_char(txn_date, 'YYYY-MM')     as month,
  count(*)                          as total_charges,
  sum(amount_cop)                   as total_cop,
  count(*) filter (where status = 'matched')          as matched,
  count(*) filter (where status = 'missing_receipt')  as missing,
  sum(amount_cop) filter (where status = 'matched')   as matched_cop,
  sum(amount_cop) filter (where status = 'missing_receipt') as missing_cop
from receipts
where status != 'skipped'
group by 1
order by 1 desc;

-- Missing receipts (for follow-up)
create or replace view missing_receipts as
select
  id,
  vendor,
  txn_date,
  amount_cop,
  created_at
from receipts
where status = 'missing_receipt'
order by txn_date desc;
