BEGIN TRANSACTION;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

GO

-- Running upgrade  -> 0001

CREATE TABLE login_throttles (
    [key] VARCHAR(64) NOT NULL, 
    attempts INTEGER NOT NULL, 
    locked_until DATETIME NULL, 
    PRIMARY KEY ([key])
);

GO

CREATE TABLE settings (
    id INTEGER NOT NULL IDENTITY, 
    revision INTEGER NOT NULL, 
    store_name NVARCHAR(150) NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_single_store CHECK (id = 1)
);

GO

CREATE TABLE users (
    id INTEGER NOT NULL IDENTITY, 
    username VARCHAR(64) NOT NULL, 
    full_name NVARCHAR(150) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(15) NOT NULL, 
    is_active BIT NOT NULL, 
    created_by INTEGER NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_role CHECK (role IN ('admin','employee')), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    UNIQUE (username)
);

GO

CREATE TABLE audit_logs (
    id INTEGER NOT NULL IDENTITY, 
    user_id INTEGER NULL, 
    action VARCHAR(64) NOT NULL, 
    entity_type VARCHAR(64) NOT NULL, 
    entity_id INTEGER NULL, 
    before_json NVARCHAR(max) NULL, 
    after_json NVARCHAR(max) NULL, 
    reason NVARCHAR(2000) NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

GO

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

GO

CREATE INDEX ix_audit_logs_entity_id ON audit_logs (entity_id);

GO

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

GO

CREATE TABLE auth_sessions (
    token_hash VARCHAR(64) NOT NULL, 
    csrf_hash VARCHAR(64) NOT NULL, 
    user_id INTEGER NOT NULL, 
    expires_at DATETIME NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (token_hash), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

GO

CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at);

GO

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

GO

CREATE TABLE cash_sessions (
    id INTEGER NOT NULL IDENTITY, 
    drawer_id INTEGER NOT NULL, 
    business_date DATETIME NOT NULL, 
    responsible_user_id INTEGER NOT NULL, 
    created_by INTEGER NOT NULL, 
    previous_session_id INTEGER NULL, 
    opening_cash NUMERIC(18, 2) NOT NULL, 
    total_sales NUMERIC(18, 2) NOT NULL, 
    pos_sales NUMERIC(18, 2) NOT NULL, 
    status VARCHAR(10) NOT NULL, 
    version INTEGER NOT NULL, 
    actual_cash NUMERIC(18, 2) NULL, 
    counted_at DATETIME NULL, 
    count_version INTEGER NULL, 
    counted_by INTEGER NULL, 
    notes NVARCHAR(2000) NOT NULL, 
    closed_at DATETIME NULL, 
    closed_by INTEGER NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_closed_count CHECK (status <> 'closed' OR (actual_cash IS NOT NULL AND closed_at IS NOT NULL AND closed_by IS NOT NULL AND count_version IS NOT NULL AND count_version = version)), 
    CONSTRAINT ck_session_status CHECK (status IN ('open','closed')), 
    CONSTRAINT ck_actual_cash CHECK (actual_cash IS NULL OR actual_cash >= 0), 
    CONSTRAINT ck_single_drawer CHECK (drawer_id = 1), 
    CONSTRAINT ck_session_amounts CHECK (opening_cash >= 0 AND total_sales >= 0 AND pos_sales >= 0 AND total_sales >= pos_sales), 
    FOREIGN KEY(closed_by) REFERENCES users (id), 
    FOREIGN KEY(counted_by) REFERENCES users (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(previous_session_id) REFERENCES cash_sessions (id), 
    FOREIGN KEY(responsible_user_id) REFERENCES users (id), 
    CONSTRAINT uq_drawer_date UNIQUE (drawer_id, business_date)
);

GO

CREATE INDEX ix_cash_sessions_business_date ON cash_sessions (business_date);

GO

CREATE UNIQUE INDEX uq_one_open_drawer ON cash_sessions (drawer_id) WHERE status = 'open';

GO

CREATE TABLE customers (
    id INTEGER NOT NULL IDENTITY, 
    name NVARCHAR(150) NOT NULL, 
    phone NVARCHAR(40) NULL, 
    notes NVARCHAR(2000) NOT NULL, 
    created_by INTEGER NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(created_by) REFERENCES users (id)
);

GO

CREATE INDEX ix_customers_name ON customers (name);

GO

CREATE TABLE idempotency_records (
    id INTEGER NOT NULL IDENTITY, 
    user_id INTEGER NOT NULL, 
    request_key VARCHAR(64) NOT NULL, 
    request_hash VARCHAR(64) NOT NULL, 
    response_json NVARCHAR(max) NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT uq_idempotency_user_key UNIQUE (user_id, request_key)
);

GO

CREATE TABLE closing_snapshots (
    id INTEGER NOT NULL IDENTITY, 
    session_id INTEGER NOT NULL, 
    approved_by INTEGER NOT NULL, 
    approved_at DATETIME NOT NULL, 
    totals_json NVARCHAR(max) NOT NULL, 
    note NVARCHAR(2000) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id), 
    FOREIGN KEY(session_id) REFERENCES cash_sessions (id)
);

GO

CREATE INDEX ix_closing_snapshots_session_id ON closing_snapshots (session_id);

GO

CREATE TABLE customer_debts (
    id INTEGER NOT NULL IDENTITY, 
    customer_id INTEGER NOT NULL, 
    debt_date DATETIME NOT NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    due_date DATETIME NULL, 
    kind VARCHAR(10) NOT NULL, 
    session_id INTEGER NULL, 
    notes NVARCHAR(2000) NOT NULL, 
    created_by INTEGER NOT NULL, 
    cancelled_at DATETIME NULL, 
    cancelled_by INTEGER NULL, 
    cancellation_reason NVARCHAR(1000) NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_debt_origin CHECK ((kind = 'opening' AND session_id IS NULL) OR (kind = 'credit' AND session_id IS NOT NULL)), 
    CONSTRAINT ck_debt_positive CHECK (amount > 0), 
    CONSTRAINT ck_due_date CHECK (due_date IS NULL OR due_date >= debt_date), 
    FOREIGN KEY(cancelled_by) REFERENCES users (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(customer_id) REFERENCES customers (id), 
    FOREIGN KEY(session_id) REFERENCES cash_sessions (id)
);

GO

CREATE INDEX ix_customer_debts_customer_id ON customer_debts (customer_id);

GO

CREATE INDEX ix_customer_debts_debt_date ON customer_debts (debt_date);

GO

CREATE INDEX ix_customer_debts_session_id ON customer_debts (session_id);

GO

CREATE TABLE purchases (
    id INTEGER NOT NULL IDENTITY, 
    session_id INTEGER NOT NULL, 
    purchase_date DATETIME NOT NULL, 
    description NVARCHAR(250) NOT NULL, 
    supplier NVARCHAR(150) NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    payment_method VARCHAR(10) NOT NULL, 
    from_drawer BIT NOT NULL, 
    invoice_number NVARCHAR(80) NULL, 
    notes NVARCHAR(2000) NOT NULL, 
    created_by INTEGER NOT NULL, 
    cancelled_at DATETIME NULL, 
    cancelled_by INTEGER NULL, 
    cancellation_reason NVARCHAR(1000) NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_purchase_drawer CHECK (from_drawer = 0 OR payment_method = 'cash'), 
    CONSTRAINT ck_purchase_method CHECK (payment_method IN ('cash','card','bank')), 
    CONSTRAINT ck_purchase_positive CHECK (amount > 0), 
    FOREIGN KEY(cancelled_by) REFERENCES users (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(session_id) REFERENCES cash_sessions (id)
);

GO

CREATE INDEX ix_purchases_session_id ON purchases (session_id);

GO

CREATE TABLE debt_payments (
    id INTEGER NOT NULL IDENTITY, 
    debt_id INTEGER NOT NULL, 
    session_id INTEGER NOT NULL, 
    payment_date DATETIME NOT NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    payment_method VARCHAR(10) NOT NULL, 
    notes NVARCHAR(2000) NOT NULL, 
    created_by INTEGER NOT NULL, 
    cancelled_at DATETIME NULL, 
    cancelled_by INTEGER NULL, 
    cancellation_reason NVARCHAR(1000) NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_payment_method CHECK (payment_method IN ('cash','card','bank')), 
    CONSTRAINT ck_payment_positive CHECK (amount > 0), 
    FOREIGN KEY(cancelled_by) REFERENCES users (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(debt_id) REFERENCES customer_debts (id), 
    FOREIGN KEY(session_id) REFERENCES cash_sessions (id)
);

GO

CREATE INDEX ix_debt_payments_debt_id ON debt_payments (debt_id);

GO

CREATE INDEX ix_debt_payments_session_id ON debt_payments (session_id);

GO

CREATE TABLE cash_movements (
    id INTEGER NOT NULL IDENTITY, 
    session_id INTEGER NOT NULL, 
    movement_date DATETIME NOT NULL, 
    kind VARCHAR(15) NOT NULL, 
    amount NUMERIC(18, 2) NOT NULL, 
    description NVARCHAR(250) NOT NULL, 
    responsible_user_id INTEGER NOT NULL, 
    purchase_id INTEGER NULL, 
    debt_payment_id INTEGER NULL, 
    created_by INTEGER NOT NULL, 
    cancelled_at DATETIME NULL, 
    cancelled_by INTEGER NULL, 
    cancellation_reason NVARCHAR(1000) NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_movement_source CHECK ((kind IN ('expense','withdrawal','deposit','refund') AND purchase_id IS NULL AND debt_payment_id IS NULL) OR (kind = 'purchase' AND purchase_id IS NOT NULL AND debt_payment_id IS NULL) OR (kind = 'collection' AND debt_payment_id IS NOT NULL AND purchase_id IS NULL)), 
    CONSTRAINT ck_movement_positive CHECK (amount > 0), 
    FOREIGN KEY(cancelled_by) REFERENCES users (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(debt_payment_id) REFERENCES debt_payments (id), 
    FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
    FOREIGN KEY(responsible_user_id) REFERENCES users (id), 
    FOREIGN KEY(session_id) REFERENCES cash_sessions (id)
);

GO

CREATE INDEX ix_cash_movements_session_id ON cash_movements (session_id);

GO

CREATE UNIQUE INDEX uq_payment_movement ON cash_movements (debt_payment_id) WHERE debt_payment_id IS NOT NULL;

GO

CREATE UNIQUE INDEX uq_purchase_movement ON cash_movements (purchase_id) WHERE purchase_id IS NOT NULL;

GO

SET IDENTITY_INSERT settings ON;

GO

INSERT INTO settings (id, revision, store_name, currency, timezone, created_at, updated_at) VALUES (1, 0, N'متجري', 'SAR', 'Asia/Riyadh', '2026-10-27 22:40:26.025666', '2026-10-27 22:40:26.025666');

GO

SET IDENTITY_INSERT settings OFF;

GO

INSERT INTO alembic_version (version_num) OUTPUT inserted.version_num VALUES ('0001');

GO

-- Running upgrade 0001 -> 0002

CREATE TRIGGER tr_audit_logs_immutable ON audit_logs INSTEAD OF UPDATE, DELETE AS BEGIN SET NOCOUNT ON; THROW 51000, 'Approved records are append-only', 1; END;

GO

CREATE TRIGGER tr_closing_snapshots_immutable ON closing_snapshots INSTEAD OF UPDATE, DELETE AS BEGIN SET NOCOUNT ON; THROW 51000, 'Approved records are append-only', 1; END;

GO

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

GO

COMMIT;

GO

