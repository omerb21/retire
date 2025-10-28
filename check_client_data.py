import psycopg2
from psycopg2 import sql

def check_client_data():
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname="retire",
            user="postgres",
            password="postgres",
            host="localhost",
            port="5432"
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Check capital assets for client 4
        print("\n=== Capital Assets for Client 4 ===")
        cur.execute("""
            SELECT 
                id, 
                client_id, 
                ROUND(CAST(current_value AS numeric), 2) as current_value,
                ROUND(CAST(monthly_income AS numeric), 2) as monthly_income,
                description
            FROM 
                capital_assets 
            WHERE 
                client_id = 4;
        """)
        
        print("\nCapital Assets:")
        for row in cur.fetchall():
            print(f"ID: {row[0]}, Current Value: {row[2]}, Monthly Income: {row[3]}, Description: {row[4]}")
        
        # Check employer grants for client 4
        print("\n=== Employer Grants for Client 4 ===")
        cur.execute("""
            SELECT 
                id, 
                client_id, 
                ROUND(CAST(amount AS numeric), 2) as amount,
                service_years,
                ROUND(CAST(amount / NULLIF(service_years, 0) AS numeric), 2) as monthly_avg,
                plan_name
            FROM 
                employer_grants 
            WHERE 
                client_id = 4
                AND grant_type = 'severance';
        """)
        
        print("\nSeverance Grants:")
        for row in cur.fetchall():
            print(f"ID: {row[0]}, Amount: {row[2]}, Service Years: {row[3]}, Monthly Avg: {row[4]}, Plan: {row[5]}")
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_client_data()
