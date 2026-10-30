-- Optional reporting views only. The notification worker uses the API instead.
CREATE OR REPLACE VIEW n8n_off_device_entries AS
SELECT s.id AS shift_id,s.business_date,u.id AS employee_id,u.full_name AS employee,
       v.number AS version,e.name AS item_name,e.item_code,e.quantity,e.amount,
       (s.approved_version=s.current_version) AS approved
FROM shifts s
JOIN shift_users u ON u.id=s.employee_id
JOIN shift_versions v ON v.shift_id=s.id AND v.number=s.current_version
JOIN shift_entries e ON e.version_id=v.id
WHERE e.kind='off_device';

CREATE OR REPLACE VIEW n8n_employee_monthly_summary AS
WITH entry_totals AS (
 SELECT version_id,
   SUM(CASE WHEN kind='off_device' THEN amount ELSE 0 END) AS outside_sales,
   SUM(CASE WHEN kind='debt' THEN amount ELSE 0 END) AS new_debts,
   SUM(CASE WHEN kind='purchase' THEN amount ELSE 0 END) AS cash_purchases,
   SUM(CASE WHEN kind='bank' AND purpose='current_shift' THEN amount ELSE 0 END) AS shift_bank,
   SUM(CASE WHEN kind='bank' AND purpose='customer_account' THEN amount ELSE 0 END) AS account_bank
 FROM shift_entries GROUP BY version_id
), per_shift AS (
 SELECT s.id,s.employee_id,u.full_name AS employee,date_trunc('month',s.business_date)::date AS business_month,
        v.device_sales+COALESCE(e.outside_sales,0) AS total_sales,
        COALESCE(e.new_debts,0) AS new_debts,COALESCE(e.cash_purchases,0) AS cash_purchases,
        COALESCE(e.shift_bank,0) AS shift_bank,COALESCE(e.account_bank,0) AS account_bank,
        CASE WHEN s.approved_version=s.current_version THEN (a.totals_json::jsonb->>'shortage')::numeric(18,2) ELSE 0 END AS shortage,
        CASE WHEN s.approved_version=s.current_version THEN (a.totals_json::jsonb->>'surplus')::numeric(18,2) ELSE 0 END AS surplus,
        CASE WHEN s.approved_version=s.current_version THEN 0 ELSE 1 END AS pending
 FROM shifts s JOIN shift_users u ON u.id=s.employee_id
 JOIN shift_versions v ON v.shift_id=s.id AND v.number=s.current_version
 LEFT JOIN entry_totals e ON e.version_id=v.id
 LEFT JOIN shift_approvals a ON a.version_id=v.id
)
SELECT employee_id,employee,business_month,COUNT(*) AS shift_count,
 SUM(total_sales) AS total_sales,SUM(new_debts) AS new_debts,SUM(cash_purchases) AS cash_purchases,
 SUM(shift_bank) AS current_shift_bank,SUM(account_bank) AS previous_account_bank,
 SUM(shortage) AS total_shortages,SUM(surplus) AS total_surpluses,
 SUM(surplus)-SUM(shortage) AS net_cash_difference,SUM(pending) AS pending_count
FROM per_shift GROUP BY employee_id,employee,business_month;

-- Create a dedicated read-only login separately; set its password with \password.
-- CREATE ROLE bin_doul_n8n_reader LOGIN;
-- GRANT CONNECT ON DATABASE bin_doul TO bin_doul_n8n_reader;
-- GRANT USAGE ON SCHEMA public TO bin_doul_n8n_reader;
-- GRANT SELECT ON n8n_off_device_entries,n8n_employee_monthly_summary TO bin_doul_n8n_reader;
