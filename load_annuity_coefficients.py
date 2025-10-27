"""
טעינת טבלאות מקדמי קצבה למסד הנתונים
"""
import sqlite3
import csv
import os

DB_PATH = 'retire.db'
CSV_DIR = 'MEKEDMIM'

def load_csv_to_table(conn, csv_file, table_name, create_sql):
    """טוען CSV לטבלה"""
    cursor = conn.cursor()
    
    # מחיקה ויצירת טבלה
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    cursor.execute(create_sql)
    
    # קריאת CSV וטעינה
    csv_path = os.path.join(CSV_DIR, csv_file)
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        if not rows:
            print(f"⚠️  {csv_file} ריק")
            return
        
        # בניית INSERT
        columns = list(rows[0].keys())
        placeholders = ','.join(['?' for _ in columns])
        insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
        
        # הכנסת נתונים
        for row in rows:
            values = [row[col] for col in columns]
            cursor.execute(insert_sql, values)
        
        print(f"✅ נטענו {len(rows)} שורות ל-{table_name}")
    
    conn.commit()

def main():
    print("🔄 מתחיל טעינת מקדמי קצבה...")
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. policy_generation_coefficient
    load_csv_to_table(
        conn,
        'policy_generation_coefficient.csv',
        'policy_generation_coefficient',
        """
        CREATE TABLE policy_generation_coefficient (
          id INTEGER PRIMARY KEY,
          generation_code TEXT NOT NULL,
          generation_label TEXT NOT NULL,
          net_rate REAL,
          guarantee_months INTEGER,
          age INTEGER NOT NULL,
          male_coefficient REAL,
          female_coefficient REAL,
          valid_from TEXT,
          valid_to TEXT,
          notes TEXT
        )
        """
    )
    
    # 2. product_to_generation_map
    load_csv_to_table(
        conn,
        'product_to_generation_map.csv',
        'product_to_generation_map',
        """
        CREATE TABLE product_to_generation_map (
          id INTEGER PRIMARY KEY,
          product_type TEXT NOT NULL,
          rule_from_date TEXT,
          rule_to_date TEXT,
          generation_code TEXT NOT NULL
        )
        """
    )
    
    # 3. company_annuity_coefficient
    load_csv_to_table(
        conn,
        'company_annuity_coefficient.csv',
        'company_annuity_coefficient',
        """
        CREATE TABLE company_annuity_coefficient (
          id INTEGER PRIMARY KEY,
          company_name TEXT NOT NULL,
          option_name TEXT NOT NULL,
          sex TEXT NOT NULL,
          age INTEGER NOT NULL,
          base_year INTEGER NOT NULL,
          base_coefficient REAL NOT NULL,
          annual_increment_rate REAL NOT NULL,
          notes TEXT,
          valid_from TEXT,
          valid_to TEXT
        )
        """
    )
    
    # 4. pension_fund_coefficient
    load_csv_to_table(
        conn,
        'pension_fund_coefficient.csv',
        'pension_fund_coefficient',
        """
        CREATE TABLE pension_fund_coefficient (
          id INTEGER PRIMARY KEY,
          fund_name TEXT NOT NULL,
          survivors_option TEXT NOT NULL,
          sex TEXT NOT NULL,
          retirement_age INTEGER NOT NULL,
          spouse_age_diff INTEGER NOT NULL,
          base_coefficient REAL NOT NULL,
          adjust_percent REAL NOT NULL,
          notes TEXT,
          valid_from TEXT,
          valid_to TEXT
        )
        """
    )
    
    conn.close()
    print("\n✅ טעינת מקדמי קצבה הושלמה בהצלחה!")

if __name__ == '__main__':
    main()
