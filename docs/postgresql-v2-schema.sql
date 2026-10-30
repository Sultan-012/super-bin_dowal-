BEGIN;

CREATE TABLE shift_alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT shift_alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20261029_01

CREATE TABLE shift_customers (
    id SERIAL NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    name_key VARCHAR(64) NOT NULL, 
    notes TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name_key)
);

CREATE TABLE shift_idempotency (
    id SERIAL NOT NULL, 
    actor_key VARCHAR(80) NOT NULL, 
    request_key VARCHAR(64) NOT NULL, 
    request_hash VARCHAR(64) NOT NULL, 
    response_json TEXT NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_shift_idempotency UNIQUE (actor_key, request_key)
);

CREATE TABLE shift_login_throttles (
    key VARCHAR(64) NOT NULL, 
    attempts INTEGER NOT NULL, 
    locked_until TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (key)
);

CREATE TABLE shift_settings (
    id SERIAL NOT NULL, 
    revision INTEGER NOT NULL, 
    store_name VARCHAR(150) NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    initial_opening_cash NUMERIC(18, 2) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_shift_store CHECK (id = 1 AND currency = 'YER' AND initial_opening_cash >= 0)
);

CREATE TABLE shift_users (
    id SERIAL NOT NULL, 
    username VARCHAR(64) NOT NULL, 
    full_name VARCHAR(150) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(12) NOT NULL, 
    active BOOLEAN NOT NULL, 
    created_by INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_shift_role CHECK (role IN ('admin','employee')), 
    FOREIGN KEY(created_by) REFERENCES shift_users (id), 
    UNIQUE (username)
);

CREATE TABLE shift_audit_logs (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    action VARCHAR(64) NOT NULL, 
    entity_type VARCHAR(50) NOT NULL, 
    entity_id VARCHAR(64), 
    detail_json TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES shift_users (id)
);

CREATE INDEX ix_shift_audit_logs_created_at ON shift_audit_logs (created_at);

CREATE INDEX ix_shift_audit_logs_entity_id ON shift_audit_logs (entity_id);

CREATE TABLE shift_auth_sessions (
    token_hash VARCHAR(64) NOT NULL, 
    csrf_hash VARCHAR(64) NOT NULL, 
    user_id INTEGER NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (token_hash), 
    FOREIGN KEY(user_id) REFERENCES shift_users (id)
);

CREATE INDEX ix_shift_auth_sessions_expires_at ON shift_auth_sessions (expires_at);

CREATE INDEX ix_shift_auth_sessions_user_id ON shift_auth_sessions (user_id);

CREATE TABLE shifts (
    id SERIAL NOT NULL, 
    employee_id INTEGER NOT NULL, 
    business_date DATE NOT NULL, 
    current_version INTEGER NOT NULL, 
    approved_version INTEGER, 
    previous_shift_id INTEGER, 
    submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(employee_id) REFERENCES shift_users (id), 
    FOREIGN KEY(previous_shift_id) REFERENCES shifts (id)
);

CREATE INDEX ix_shifts_business_date ON shifts (business_date);

CREATE INDEX ix_shifts_employee_id ON shifts (employee_id);

CREATE TABLE shift_attachments (
    id VARCHAR(36) NOT NULL, 
    owner_id INTEGER NOT NULL, 
    shift_id INTEGER, 
    filename VARCHAR(150) NOT NULL, 
    mime_type VARCHAR(30) NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    size INTEGER NOT NULL, 
    content BYTEA NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_attachment_size CHECK (size > 0 AND size <= 5242880), 
    FOREIGN KEY(owner_id) REFERENCES shift_users (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id)
);

CREATE INDEX ix_shift_attachments_shift_id ON shift_attachments (shift_id);

CREATE TABLE shift_customer_debts (
    id SERIAL NOT NULL, 
    customer_id INTEGER NOT NULL, 
    invoice_number VARCHAR(100) NOT NULL, 
    description TEXT NOT NULL, 
    debt_date DATE NOT NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    source_key VARCHAR(36), 
    shift_id INTEGER, 
    active BOOLEAN NOT NULL, 
    created_by INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_shift_debt_amount CHECK (amount > 0), 
    FOREIGN KEY(created_by) REFERENCES shift_users (id), 
    FOREIGN KEY(customer_id) REFERENCES shift_customers (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id), 
    UNIQUE (source_key)
);

CREATE INDEX ix_shift_customer_debts_customer_id ON shift_customer_debts (customer_id);

CREATE INDEX ix_shift_customer_debts_debt_date ON shift_customer_debts (debt_date);

CREATE INDEX ix_shift_customer_debts_shift_id ON shift_customer_debts (shift_id);

CREATE TABLE shift_notification_events (
    id SERIAL NOT NULL, 
    event_key VARCHAR(160) NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    shift_id INTEGER, 
    payload_json TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id), 
    UNIQUE (event_key)
);

CREATE INDEX ix_shift_notification_events_kind ON shift_notification_events (kind);

CREATE TABLE shift_references (
    id SERIAL NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    normalized_key VARCHAR(64) NOT NULL, 
    shift_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id), 
    CONSTRAINT uq_shift_reference UNIQUE (kind, normalized_key)
);

CREATE TABLE shift_versions (
    id SERIAL NOT NULL, 
    shift_id INTEGER NOT NULL, 
    number INTEGER NOT NULL, 
    business_date DATE NOT NULL, 
    deposit_date DATE NOT NULL, 
    deposit_number VARCHAR(100) NOT NULL, 
    deposit_amount NUMERIC(18, 2) NOT NULL, 
    device_sales NUMERIC(18, 2) NOT NULL, 
    opening_cash NUMERIC(18, 2), 
    pos_sales NUMERIC(18, 2), 
    retained_cash NUMERIC(18, 2), 
    notes TEXT NOT NULL, 
    reason VARCHAR(1000) NOT NULL, 
    created_by INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_shift_count_fields CHECK ((opening_cash IS NULL AND pos_sales IS NULL AND retained_cash IS NULL) OR (opening_cash >= 0 AND pos_sales >= 0 AND retained_cash >= 0 AND opening_cash IS NOT NULL AND pos_sales IS NOT NULL AND retained_cash IS NOT NULL)), 
    CONSTRAINT ck_shift_version_money CHECK (deposit_amount >= 0 AND device_sales >= 0), 
    CONSTRAINT ck_shift_deposit_number CHECK (length(trim(deposit_number)) > 0), 
    FOREIGN KEY(created_by) REFERENCES shift_users (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id), 
    CONSTRAINT uq_shift_version UNIQUE (shift_id, number)
);

CREATE INDEX ix_shift_versions_business_date ON shift_versions (business_date);

CREATE INDEX ix_shift_versions_shift_id ON shift_versions (shift_id);

CREATE TABLE shift_approvals (
    id SERIAL NOT NULL, 
    shift_id INTEGER NOT NULL, 
    version_id INTEGER NOT NULL, 
    totals_json TEXT NOT NULL, 
    note VARCHAR(1000) NOT NULL, 
    approved_by INTEGER NOT NULL, 
    approved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(approved_by) REFERENCES shift_users (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id), 
    FOREIGN KEY(version_id) REFERENCES shift_versions (id), 
    UNIQUE (version_id)
);

CREATE INDEX ix_shift_approvals_shift_id ON shift_approvals (shift_id);

CREATE TABLE shift_debt_payments (
    id SERIAL NOT NULL, 
    debt_id INTEGER NOT NULL, 
    shift_id INTEGER NOT NULL, 
    source_key VARCHAR(36) NOT NULL, 
    payment_date DATE NOT NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    method VARCHAR(10) NOT NULL, 
    active BOOLEAN NOT NULL, 
    created_by INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_shift_debt_payment CHECK (amount > 0 AND method = 'bank'), 
    FOREIGN KEY(created_by) REFERENCES shift_users (id), 
    FOREIGN KEY(debt_id) REFERENCES shift_customer_debts (id), 
    FOREIGN KEY(shift_id) REFERENCES shifts (id), 
    UNIQUE (source_key)
);

CREATE INDEX ix_shift_debt_payments_debt_id ON shift_debt_payments (debt_id);

CREATE INDEX ix_shift_debt_payments_shift_id ON shift_debt_payments (shift_id);

CREATE TABLE shift_entries (
    id SERIAL NOT NULL, 
    version_id INTEGER NOT NULL, 
    line_key VARCHAR(36) NOT NULL, 
    kind VARCHAR(15) NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    reference VARCHAR(100) NOT NULL, 
    description TEXT NOT NULL, 
    item_code VARCHAR(100) NOT NULL, 
    quantity INTEGER, 
    invoice_number VARCHAR(100) NOT NULL, 
    invoice_total NUMERIC(18, 2), 
    purpose VARCHAR(25), 
    attachment_id VARCHAR(36), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_bank_required CHECK (kind <> 'bank' OR (length(trim(reference)) > 0 AND purpose IN ('current_shift','customer_account') AND purpose IS NOT NULL)), 
    CONSTRAINT ck_debt_invoice_required CHECK (kind <> 'debt' OR (length(trim(description)) > 0 AND invoice_total >= amount AND invoice_total IS NOT NULL)), 
    CONSTRAINT ck_off_device_required CHECK (kind <> 'off_device' OR (length(trim(item_code)) > 0 AND quantity > 0 AND quantity IS NOT NULL)), 
    CONSTRAINT ck_purchase_invoice_required CHECK (kind <> 'purchase' OR length(trim(description)) > 0), 
    CONSTRAINT ck_shift_entry_kind CHECK (kind IN ('purchase','off_device','debt','bank')), 
    CONSTRAINT ck_shift_entry_amount_name CHECK (amount > 0 AND length(trim(name)) > 0), 
    FOREIGN KEY(attachment_id) REFERENCES shift_attachments (id), 
    FOREIGN KEY(version_id) REFERENCES shift_versions (id), 
    CONSTRAINT uq_shift_line_key UNIQUE (version_id, line_key)
);

CREATE INDEX ix_shift_entries_kind ON shift_entries (kind);

CREATE INDEX ix_shift_entries_version_id ON shift_entries (version_id);

CREATE INDEX ix_shift_entry_version_kind ON shift_entries (version_id, kind);

CREATE TABLE shift_notification_deliveries (
    id SERIAL NOT NULL, 
    event_id INTEGER NOT NULL, 
    channel VARCHAR(12) NOT NULL, 
    status VARCHAR(15) NOT NULL, 
    lease_hash VARCHAR(64), 
    claim_key VARCHAR(64), 
    lease_until TIMESTAMP WITHOUT TIME ZONE, 
    attempts INTEGER NOT NULL, 
    provider_reference VARCHAR(200) NOT NULL, 
    last_error VARCHAR(500) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_delivery_channel CHECK (channel IN ('email','whatsapp')), 
    CONSTRAINT ck_delivery_status CHECK (status IN ('pending','leased','sent','uncertain','cancelled')), 
    FOREIGN KEY(event_id) REFERENCES shift_notification_events (id), 
    UNIQUE (claim_key), 
    CONSTRAINT uq_shift_event_channel UNIQUE (event_id, channel)
);

CREATE INDEX ix_shift_notification_deliveries_event_id ON shift_notification_deliveries (event_id);

CREATE INDEX ix_shift_notification_deliveries_status ON shift_notification_deliveries (status);

CREATE TABLE shift_invoice_reviews (
    id SERIAL NOT NULL, 
    entry_id INTEGER NOT NULL, 
    status VARCHAR(12) NOT NULL, 
    note VARCHAR(1000) NOT NULL, 
    debt_id INTEGER, 
    reviewed_by INTEGER, 
    reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_invoice_review_status CHECK (status IN ('pending','matched')), 
    FOREIGN KEY(debt_id) REFERENCES shift_customer_debts (id), 
    FOREIGN KEY(entry_id) REFERENCES shift_entries (id), 
    FOREIGN KEY(reviewed_by) REFERENCES shift_users (id), 
    UNIQUE (entry_id)
);

CREATE INDEX ix_shift_invoice_reviews_status ON shift_invoice_reviews (status);

INSERT INTO shift_alembic_version (version_num) VALUES ('20261029_01') RETURNING shift_alembic_version.version_num;

-- Running upgrade 20261029_01 -> 20261029_02

INSERT INTO shift_settings (id, revision, store_name, currency, timezone, initial_opening_cash) VALUES (1, 0, 'سوبر ماركت بن دول', 'YER', 'Asia/Aden', 0.00);

CREATE FUNCTION shift_forbid_financial_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Financial records are append-only; create a new version'; END; $$;

CREATE TRIGGER protect_shift_versions BEFORE UPDATE OR DELETE ON shift_versions FOR EACH ROW EXECUTE FUNCTION shift_forbid_financial_change();

CREATE TRIGGER protect_shift_entries BEFORE UPDATE OR DELETE ON shift_entries FOR EACH ROW EXECUTE FUNCTION shift_forbid_financial_change();

CREATE TRIGGER protect_shift_approvals BEFORE UPDATE OR DELETE ON shift_approvals FOR EACH ROW EXECUTE FUNCTION shift_forbid_financial_change();

CREATE TRIGGER protect_shift_audit_logs BEFORE UPDATE OR DELETE ON shift_audit_logs FOR EACH ROW EXECUTE FUNCTION shift_forbid_financial_change();

CREATE TRIGGER protect_shift_notification_events BEFORE UPDATE OR DELETE ON shift_notification_events FOR EACH ROW EXECUTE FUNCTION shift_forbid_financial_change();

UPDATE shift_alembic_version SET version_num='20261029_02' WHERE shift_alembic_version.version_num = '20261029_01';

COMMIT;

