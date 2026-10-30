-- Run after migrations, using a database administrator in DailySales.
-- First create Login in SSMS with your own credentials, and its database user.
-- This script contains no passwords. Review the user name before applying.
USE DailySales;
GO
CREATE ROLE daily_sales_runtime;
GO
GRANT SELECT ON SCHEMA::dbo TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.users TO daily_sales_runtime;
GRANT INSERT, DELETE ON dbo.auth_sessions TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.login_throttles TO daily_sales_runtime;
GRANT UPDATE ON dbo.settings TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.cash_sessions TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.customers TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.customer_debts TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.debt_payments TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.purchases TO daily_sales_runtime;
GRANT INSERT, UPDATE ON dbo.cash_movements TO daily_sales_runtime;
GRANT INSERT ON dbo.audit_logs TO daily_sales_runtime;
GRANT INSERT ON dbo.closing_snapshots TO daily_sales_runtime;
GRANT INSERT ON dbo.idempotency_records TO daily_sales_runtime;
DENY UPDATE, DELETE ON dbo.audit_logs TO daily_sales_runtime;
DENY UPDATE, DELETE ON dbo.closing_snapshots TO daily_sales_runtime;
DENY DELETE ON dbo.cash_sessions TO daily_sales_runtime;
DENY DELETE ON dbo.customers TO daily_sales_runtime;
DENY DELETE ON dbo.customer_debts TO daily_sales_runtime;
DENY DELETE ON dbo.debt_payments TO daily_sales_runtime;
DENY DELETE ON dbo.purchases TO daily_sales_runtime;
DENY DELETE ON dbo.cash_movements TO daily_sales_runtime;
DENY UPDATE, DELETE ON dbo.idempotency_records TO daily_sales_runtime;
GO
ALTER ROLE daily_sales_runtime ADD MEMBER DailySalesApp;
GO
