import sqlite3
import openpyxl
from datetime import datetime, date
import os

excel_path = "/Users/davidabrilperrig/dev/MisCuentas/cuentas 2026 Erica (1).xlsx"
if not os.path.exists(excel_path):
    excel_path = "/Users/davidabrilperrig/Dev/MisCuentas/cuentas 2026 Erica (1).xlsx"

db_path = "/Users/davidabrilperrig/dev/MisCuentas/miscuentas.db"

def get_db_connection():
    return sqlite3.connect(db_path)

def migrate_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(accounts)")
    cols = [c[1] for c in cur.fetchall()]
    if "is_credit_card" not in cols:
        print("Migrating database: adding is_credit_card column to accounts")
        cur.execute("ALTER TABLE accounts ADD COLUMN is_credit_card INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    conn.close()

def create_accounts(conn):
    cur = conn.cursor()
    # Check and insert accounts
    accounts = [
        ("Tarjeta naranja Erica", "ARS", 1),
        ("Visa Black Erica", "ARS", 1),
        ("Mercado Crédito Erica", "ARS", 1),
        ("Bancor Erica", "ARS", 0)
    ]
    account_ids = {}
    for name, currency, is_cc in accounts:
        cur.execute("SELECT id FROM accounts WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            account_ids[name] = row[0]
            # Ensure it is marked as credit card if it is
            cur.execute("UPDATE accounts SET is_credit_card = ? WHERE id = ?", (is_cc, row[0]))
        else:
            cur.execute(
                "INSERT INTO accounts (name, currency, opening_balance_minor, is_credit_card) VALUES (?, ?, 0, ?)",
                (name, currency, is_cc)
            )
            account_ids[name] = cur.lastrowid
            print(f"Created account: {name} (Credit Card: {is_cc})")
    conn.commit()
    return account_ids

def create_categories(conn):
    cur = conn.cursor()
    categories = [
        ("Servicios Tarjeta", "expense"),
        ("Suscripciones Tarjeta", "expense"),
        ("Educación Tarjeta", "expense"),
        ("Compras en Cuotas", "expense"),
        ("Otros Tarjeta", "expense"),
        ("Sueldo Erica", "income")
    ]
    cat_ids = {}
    for name, kind in categories:
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            cat_ids[name] = row[0]
        else:
            cur.execute("INSERT INTO categories (name, kind) VALUES (?, ?)", (name, kind))
            cat_ids[name] = cur.lastrowid
            print(f"Created category: {name} ({kind})")
    conn.commit()
    return cat_ids

def add_recurring_rule(conn, name, kind, amount_ars, account_id, category_id, day, start_dt, end_dt, notes=""):
    cur = conn.cursor()
    # Check if a rule with this name and account already exists to avoid duplicates
    cur.execute(
        "SELECT id FROM recurring_rules WHERE name = ? AND account_id = ? AND start_date = ?",
        (name, account_id, start_dt.isoformat())
    )
    row = cur.fetchone()
    amount_minor = int(float(amount_ars) * 100)
    if row:
        # Update existing rule to make sure amount and dates are correct
        cur.execute(
            """UPDATE recurring_rules SET 
               amount_minor = ?, end_date = ?, notes = ?, category_id = ?
               WHERE id = ?""",
            (amount_minor, end_dt.isoformat() if end_dt else None, notes, category_id, row[0])
        )
    else:
        cur.execute(
            """INSERT INTO recurring_rules 
               (name, kind, amount_minor, currency, account_id, category_id, day_of_month, start_date, end_date, active, notes)
               VALUES (?, ?, ?, 'ARS', ?, ?, ?, ?, ?, 1, ?)""",
            (name, kind, amount_minor, account_id, category_id, day, start_dt.isoformat(), end_dt.isoformat() if end_dt else None, notes)
        )
        print(f"Added recurring rule: {name} ({amount_ars} ARS, Account ID: {account_id})")
    conn.commit()

def add_transaction(conn, occurred_on, name, amount_ars, account_id, category_id, notes=""):
    cur = conn.cursor()
    # Check if transaction already exists
    cur.execute(
        "SELECT id FROM transactions WHERE occurred_on = ? AND account_id = ? AND description = ?",
        (occurred_on.isoformat(), account_id, name)
    )
    row = cur.fetchone()
    amount_minor = int(float(amount_ars) * 100)
    if not row:
        cur.execute(
            """INSERT INTO transactions 
               (occurred_on, account_id, category_id, kind, amount_minor, currency, description)
               VALUES (?, ?, ?, 'expense', ?, 'ARS', ?)""",
            (occurred_on.isoformat(), account_id, category_id, amount_minor, name)
        )
        print(f"Added transaction: {name} on {occurred_on} ({amount_ars} ARS)")
    conn.commit()

def main():
    print("Starting import from Excel to SQLite DB...")
    migrate_db()
    
    conn = get_db_connection()
    account_ids = create_accounts(conn)
    cat_ids = create_categories(conn)

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    
    # --- 1. Import Naranja Card ---
    # We will import the recurring/fixed services in Naranja as RecurringRules
    # And the specific installments as RecurringRules with start/end dates.
    naranja_acc_id = account_ids["Tarjeta naranja Erica"]
    
    # We define the recurring services from Naranja sheet:
    naranja_recurring = [
        ("Cable", "Servicios Tarjeta", 92000), # June value as reference
        ("Claro Tomi", "Servicios Tarjeta", 36000),
        ("Claros", "Servicios Tarjeta", 91000),
        ("Camino de las sierras", "Servicios Tarjeta", 18000),
        ("Ecogas", "Servicios Tarjeta", 63000),
        ("Seguros telefonos", "Servicios Tarjeta", 30700),
        ("Seguros casa+Etios", "Servicios Tarjeta", 195000),
        ("Muni casa cosquin", "Servicios Tarjeta", 55400),
        ("SIPSSA", "Servicios Tarjeta", 244445),
        ("Agua", "Servicios Tarjeta", 55500),
        ("Rentas todo", "Servicios Tarjeta", 95000),
        ("Muni casa+autos", "Servicios Tarjeta", 103000),
        ("Seguro Clio", "Servicios Tarjeta", 72200),
        ("Epec", "Servicios Tarjeta", 127000),
    ]
    
    for name, cat_name, amt in naranja_recurring:
        add_recurring_rule(
            conn, 
            name=name, 
            kind="expense", 
            amount_ars=amt, 
            account_id=naranja_acc_id, 
            category_id=cat_ids[cat_name], 
            day=10, 
            start_dt=date(2026, 6, 1), 
            end_dt=None,
            notes="Servicio mensual debitado en Naranja"
        )
    
    # Let's add installment/finite items on Naranja
    # We got these from our analysis:
    naranja_installments = [
        ("facultad", 378000, date(2026, 6, 1), date(2026, 12, 1), "Facultad cuotas"),
        ("lavavajillas", 64899, date(2026, 6, 1), date(2026, 12, 1), "Lavavajillas cuotas"),
        ("farmacia (3m)", 2546, date(2026, 6, 1), date(2026, 8, 1), "Farmacia en cuotas"),
        ("vaquerias (3m)", 20000, date(2026, 6, 1), date(2026, 8, 1), "Vaquerias en cuotas"),
        ("Botas Pablo (6m)", 17333, date(2026, 6, 1), date(2026, 11, 1), "Botas Pablo cuota 1/6"),
        ("farmacia (2m)", 6000, date(2026, 6, 1), date(2026, 7, 1), "Farmacia en cuotas"),
        ("super (2m)", 4000, date(2026, 6, 1), date(2026, 7, 1), "Super en cuotas"),
        ("anteojos David (2m)", 22400, date(2026, 6, 1), date(2026, 7, 1), "Anteojos David en cuotas"),
        ("bertoldy (2m)", 8000, date(2026, 6, 1), date(2026, 7, 1), "Bertoldy en cuotas"),
        ("Bertoldi (3m)", 9100, date(2026, 6, 1), date(2026, 8, 1), "Bertoldi en cuotas"),
        ("libertad (3m)", 2550, date(2026, 6, 1), date(2026, 8, 1), "Libertad en cuotas"),
        ("pantalon David (3m)", 22130, date(2026, 6, 1), date(2026, 8, 1), "Pantalon David en cuotas"),
        ("farmacia (2m)", 5450, date(2026, 6, 1), date(2026, 7, 1), "Farmacia en cuotas"),
        ("Allende Farmacia (2m)", 5550, date(2026, 6, 1), date(2026, 7, 1), "Allende Farmacia cuota"),
        ("Farmacia (3m)", 12000, date(2026, 6, 1), date(2026, 8, 1), "Farmacia cuotas"),
        ("Farmacia (3m)", 10000, date(2026, 6, 1), date(2026, 8, 1), "Farmacia cuotas"),
        ("farmacia (2m)", 3700, date(2026, 6, 1), date(2026, 7, 1), "Farmacia cuotas"),
        ("Allende farmacia (2m)", 17533, date(2026, 6, 1), date(2026, 7, 1), "Allende farmacia cuotas"),
        ("campera cuero Erica (2m)", 23997, date(2026, 6, 1), date(2026, 7, 1), "Campera cuero Erica"),
        ("camping (3m)", 26000, date(2026, 6, 1), date(2026, 7, 1), "Camping cuotas"),
        ("nosotros", 1700000, date(2026, 6, 1), date(2026, 12, 1), "Gasto general nosotros"),
    ]
    
    for name, amt, start, end, note in naranja_installments:
        add_recurring_rule(
            conn,
            name=name,
            kind="expense",
            amount_ars=amt,
            account_id=naranja_acc_id,
            category_id=cat_ids["Compras en Cuotas"],
            day=10,
            start_dt=start,
            end_dt=end,
            notes=note
        )

    # Let's add single one-off transactions that only occurred in June 2026 on Naranja
    naranja_one_offs = [
        ("Servis Yaris", 95700),
        ("Havanna Erica", 21000),
        ("Tomas Zeta", 167233),
        ("zapatillas tomi", 30000),
        ("quivox", 42000),
        ("David", 14900),
        ("David compu carg", 52000),
        ("Salida Erica", 12832),
        ("platos", 47900),
        ("Tomas Master", 279000),
        ("David  smwebgroup", 49500),
    ]
    for name, amt in naranja_one_offs:
        add_transaction(
            conn,
            occurred_on=date(2026, 6, 10),
            name=name,
            amount_ars=amt,
            account_id=naranja_acc_id,
            category_id=cat_ids["Otros Tarjeta"],
            notes="Consumo puntual en Naranja"
        )
        
    # Also add the one-off for camping in August
    add_transaction(
        conn,
        occurred_on=date(2026, 8, 10),
        name="camping (saldo final)",
        amount_ars=13000,
        account_id=naranja_acc_id,
        category_id=cat_ids["Otros Tarjeta"]
    )

    # --- 2. Import Gastos personales Erica ---
    # Cards: Visa Black Erica ("black"), Mercado Crédito Erica ("credit merc"), Tarjeta naranja Erica ("naranja")
    black_acc_id = account_ids["Visa Black Erica"]
    merc_cred_acc_id = account_ids["Mercado Crédito Erica"]
    
    erica_personal = [
        # Card, Name, Amt, Start, End, Note
        ("black", "Pantalon", 18000, date(2026, 6, 1), date(2026, 7, 1), "Gastos personales Erica"),
        ("credit merc", "pelu adelanto", 35000, date(2026, 6, 1), date(2026, 7, 1), "Gastos personales Erica"),
        ("black", "regal Mariel", 9900, date(2026, 6, 1), date(2026, 7, 1), "Gastos personales Erica"),
        ("black", "ropa", 57333, date(2026, 6, 1), date(2026, 7, 1), "Gastos personales Erica"),
        ("credit merc", "Consumo Credit Merc", 74000, date(2026, 6, 1), date(2026, 8, 1), "Gastos personales Erica"),
        ("black", "botas", 17700, date(2026, 6, 1), date(2027, 2, 1), "Gastos personales Erica"),
        ("naranja", "Consumo Naranja", 34000, date(2026, 6, 1), date(2026, 8, 1), "Gastos personales Erica"),
    ]
    
    for card, name, amt, start, end, note in erica_personal:
        if card == "black":
            acc_id = black_acc_id
        elif card == "credit merc":
            acc_id = merc_cred_acc_id
        else:
            acc_id = naranja_acc_id
            
        add_recurring_rule(
            conn,
            name=f"Erica: {name}",
            kind="expense",
            amount_ars=amt,
            account_id=acc_id,
            category_id=cat_ids["Compras en Cuotas"],
            day=5,
            start_dt=start,
            end_dt=end,
            notes=note
        )

    # Let's add the monthly income of Erica: 250,000 ARS to Bancor Erica
    bancor_erica_id = account_ids["Bancor Erica"]
    add_recurring_rule(
        conn,
        name="Sueldo Erica",
        kind="income",
        amount_ars=250000,
        account_id=bancor_erica_id,
        category_id=cat_ids["Sueldo Erica"],
        day=5,
        start_dt=date(2026, 5, 1),
        end_dt=date(2027, 2, 1),
        notes="Sueldo mensual de Erica"
    )

    conn.close()
    print("Import completed successfully!")

if __name__ == "__main__":
    main()
