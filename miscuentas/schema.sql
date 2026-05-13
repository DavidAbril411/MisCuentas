-- MisCuentas schema.
-- Money is stored as INTEGER minor units (centavos ARS, cents USD).
-- FX is stored as INTEGER micro-ARS per 1 USD (ARS-per-USD x 1_000_000).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accounts (
    id                           INTEGER PRIMARY KEY,
    name                         TEXT    NOT NULL UNIQUE,
    currency                     TEXT    NOT NULL CHECK (currency IN ('ARS','USD')),
    opening_balance_minor        INTEGER NOT NULL DEFAULT 0,
    opening_fx_rate_to_ars_micro INTEGER,
    created_at                   TEXT    NOT NULL DEFAULT (datetime('now')),
    archived                     INTEGER NOT NULL DEFAULT 0,
    CHECK (
        (currency = 'ARS' AND opening_fx_rate_to_ars_micro IS NULL)
        OR (currency = 'USD' AND (opening_balance_minor = 0 OR opening_fx_rate_to_ars_micro IS NOT NULL))
    )
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('income','expense'))
);

CREATE TABLE IF NOT EXISTS recurring_rules (
    id            INTEGER PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS debts (
    id                   INTEGER PRIMARY KEY,
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
CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);

CREATE TABLE IF NOT EXISTS transactions (
    id                   INTEGER PRIMARY KEY,
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
CREATE INDEX IF NOT EXISTS idx_tx_occurred_on ON transactions(occurred_on);
CREATE INDEX IF NOT EXISTS idx_tx_account     ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_tx_rule        ON transactions(recurring_rule_id);
CREATE INDEX IF NOT EXISTS idx_tx_debt        ON transactions(debt_id);

CREATE TABLE IF NOT EXISTS fx_rates (
    id                INTEGER PRIMARY KEY,
    effective_on      TEXT    NOT NULL UNIQUE,
    rate_to_ars_micro INTEGER NOT NULL CHECK (rate_to_ars_micro > 0),
    source            TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fx_date ON fx_rates(effective_on);

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
END;

CREATE TRIGGER IF NOT EXISTS trg_tx_currency_match_update
BEFORE UPDATE OF account_id, currency ON transactions
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT currency FROM accounts WHERE id = NEW.account_id) != NEW.currency
        THEN RAISE(ABORT, 'La moneda del movimiento no coincide con la de la cuenta')
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
END;

CREATE TRIGGER IF NOT EXISTS trg_rule_currency_match_update
BEFORE UPDATE OF account_id, currency ON recurring_rules
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT currency FROM accounts WHERE id = NEW.account_id) != NEW.currency
        THEN RAISE(ABORT, 'La moneda de la regla no coincide con la de la cuenta')
    END;
END;
