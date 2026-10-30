-- Run as schema owner after Alembic. Never put a password in this file.
-- If the role does not yet exist, first run:
--   CREATE ROLE bin_doul_app LOGIN;
-- Then in psql, use: \password bin_doul_app
-- Point the application DATABASE_URL to this role after granting privileges.
GRANT CONNECT ON DATABASE bin_doul TO bin_doul_app;
GRANT USAGE ON SCHEMA public TO bin_doul_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bin_doul_app;

GRANT SELECT, INSERT ON
  shift_versions, shift_entries, shift_approvals, shift_audit_logs,
  shift_notification_events, shift_idempotency, shift_references
TO bin_doul_app;

GRANT SELECT, INSERT, UPDATE ON
  shift_users, shift_settings, shifts, shift_attachments,
  shift_invoice_reviews, shift_customers, shift_customer_debts,
  shift_debt_payments, shift_notification_deliveries, shift_login_throttles
TO bin_doul_app;

GRANT SELECT, INSERT, DELETE ON shift_auth_sessions TO bin_doul_app;
-- No DELETE on financial tables; no ALTER/DROP/TRUNCATE privileges.
-- Database owner or migration role remains separate from this login.
