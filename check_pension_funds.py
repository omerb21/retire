import sqlite3, os

dbs = ["retire.db", "retire-nuc.db", "test_retire.db"]

for db in dbs:
    if not os.path.exists(db):
        continue

    print("\n" + "=" * 80)
    print("DB:", db)

    con = sqlite3.connect(db)
    cur = con.cursor()

    tables = [
        r[0]
        for r in cur.execute(
            "select name from sqlite_master where type='table' order by name"
        ).fetchall()
    ]
    print("tables_count=", len(tables))
    print("has_pension_funds=", "pension_funds" in tables)

    if "pension_funds" in tables:
        rows = cur.execute(
            "select id, client_id, fund_name, balance, pension_amount, tax_treatment, input_mode, deduction_file, "
            "substr(coalesce(conversion_source,''),1,120) "
            "from pension_funds order by id desc limit 15"
        ).fetchall()

        print("pension_funds_rows_shown=", len(rows))
        for r in rows:
            print(r)

    con.close()
