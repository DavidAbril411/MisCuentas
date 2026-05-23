-- MisCuentas schema.
-- Money is stored as INTEGER minor units (centavos ARS, cents USD).
-- FX is stored as INTEGER micro-ARS per 1 USD (ARS-per-USD x 1_000_000).
-- Multi-tenant: every owned table has user_id NOT NULL referencing users(id).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (length(username) BETWEEN 3 AND 30)
);

CREATE TABLE IF NOT EXISTS accounts (
    id                           INTEGER PRIMARY KEY,
    user_id                      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                         TEXT    NOT NULL,
    currency                     TEXT    NOT NULL CHECK (currency IN ('ARS','USD')),
    opening_balance_minor        INTEGER NOT NULL DEFAULT 0,
    opening_fx_rate_to_ars_micro INTEGER,
    created_at                   TEXT    NOT NULL DEFAULT (datetime('now')),
    archived                     INTEGER NOT NULL DEFAULT 0,
    is_credit_card               INTEGER NOT NULL DEFAULT 0,
    CHECK (
        (currency = 'ARS' AND opening_fx_rate_to_ars_micro IS NULL)
        OR (currency = 'USD' AND (opening_balance_minor = 0 OR opening_fx_rate_to_ars_micro IS NOT NULL))
    ),
    UNIQUE (user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id);

CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name    TEXT    NOT NULL,
    kind    TEXT    NOT NULL CHECK (kind IN ('income','expense')),
    UNIQUE (user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_categories_user ON categories(user_id);

CREATE TABLE IF NOT EXISTS recurring_rules (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT    NOT NULL,
    kind          TEXT    NOT NULL CHECK (kind IN ('income','expense')),
    amount_minor  INTEGER NOT NULL CHECK (amount_minor > 0),
    currency      TEXT    NOT NULL CHECK (currency IN ('ARS','USD')),
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    category_id   INTEGER REFERENCES categories(id),
    day_of_month  INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 28),
    start_date    TEXT    NOT NULL,
    end_date      TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    notes         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rules_user ON recurring_rules(user_id);

CREATE TABLE IF NOT EXISTS debts (
    id                   INTEGER PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    counterparty         TEXT    NOT NULL,
    direction            TEXT    NOT NULL CHECK (direction IN ('receivable','payable')),
    principal_minor      INTEGER NOT NULL CHECK (principal_minor > 0),
    currency             TEXT    NOT NULL CHECK (currency IN ('ARS','USD')),
    fx_rate_to_ars_micro INTEGER,
    opened_on            TEXT    NOT NULL,
    due_on               TEXT,
    status               TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open','settled','partial','cancelled')),
    notes                TEXT,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (currency = 'ARS' AND fx_rate_to_ars_micro IS NULL)
        OR (currency = 'USD' AND fx_rate_to_ars_micro IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_debts_user_status ON debts(user_id, status);

CREATE TABLE IF NOT EXISTS transactions (
    id                   INTEGER PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    occurred_on          TEXT    NOT NULL,
    account_id           INTEGER NOT NULL REFERENCES accounts(id),
    category_id          INTEGER REFERENCES categories(id),
    kind                 TEXT    NOT NULL CHECK (kind IN ('income','expense','transfer_in','transfer_out')),
    amount_minor         INTEGER NOT NULL CHECK (amount_minor > 0),
    currency             TEXT    NOT NULL CHECK (currency IN ('ARS','USD')),
    fx_rate_to_ars_micro INTEGER,
    description          TEXT,
    recurring_rule_id    INTEGER REFERENCES recurring_rules(id),
    debt_id              INTEGER REFERENCES debts(id),
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (currency = 'ARS' AND fx_rate_to_ars_micro IS NULL)
        OR (currency = 'USD' AND fx_rate_to_ars_micro IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_tx_user_date    ON transactions(user_id, occurred_on);
CREATE INDEX IF NOT EXISTS idx_tx_account      ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_tx_rule         ON transactions(recurring_rule_id);
CREATE INDEX IF NOT EXISTS idx_tx_debt         ON transactions(debt_id);

CREATE TABLE IF NOT EXISTS fx_rates (
    id                INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    effective_on      TEXT    NOT NULL,
    rate_to_ars_micro INTEGER NOT NULL CHECK (rate_to_ars_micro > 0),
    source            TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, effective_on)
);
CREATE INDEX IF NOT EXISTS idx_fx_user_date ON fx_rates(user_id, effective_on);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Triggers: la moneda de un movimiento o regla recurrente debe coincidir con
-- la moneda de la cuenta asociada. Backstop a nivel DB.

CREATE TRIGGER IF NOT EXISTS trg_tx_currency_match_insert
BEFORE INSERT ON transactions
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT currency FROM accounts WHERE id = NEW.account_id) != NEW.currency
        THEN RAISE(ABORT, 'La moneda del movimiento no coincide con la de la cuenta')
    END;
    -- Tenant integrity: la cuenta debe pertenecer al mismo usuario
    SELECT CASE
        WHEN (SELECT user_id FROM accounts WHERE id = NEW.account_id) != NEW.user_id
        THEN RAISE(ABORT, 'La cuenta no pertenece al usuario del movimiento')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_tx_currency_match_update
BEFORE UPDATE OF account_id, currency, user_id ON transactions
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT currency FROM accounts WHERE id = NEW.account_id) != NEW.currency
        THEN RAISE(ABORT, 'La moneda del movimiento no coincide con la de la cuenta')
    END;
    SELECT CASE
        WHEN (SELECT user_id FROM accounts WHERE id = NEW.account_id) != NEW.user_id
        THEN RAISE(ABORT, 'La cuenta no pertenece al usuario del movimiento')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_rule_currency_match_insert
BEFORE INSERT ON recurring_rules
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT currency FROM accounts WHERE id = NEW.account_id) != NEW.currency
        THEN RAISE(ABORT, 'La moneda de la regla no coincide con la de la cuenta')
    END;
    SELECT CASE
        WHEN (SELECT user_id FROM accounts WHERE id = NEW.account_id) != NEW.user_id
        THEN RAISE(ABORT, 'La cuenta no pertenece al usuario de la regla')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_rule_currency_match_update
BEFORE UPDATE OF account_id, currency, user_id ON recurring_rules
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT currency FROM accounts WHERE id = NEW.account_id) != NEW.currency
        THEN RAISE(ABORT, 'La moneda de la regla no coincide con la de la cuenta')
    END;
    SELECT CASE
        WHEN (SELECT user_id FROM accounts WHERE id = NEW.account_id) != NEW.user_id
        THEN RAISE(ABORT, 'La cuenta no pertenece al usuario de la regla')
    END;
END;
