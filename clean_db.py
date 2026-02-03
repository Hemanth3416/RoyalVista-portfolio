
import sqlite3
import os

def clean_database():
    db_path = 'instance/site.db'
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Tables to keep (don't wipe these)
    # 1. user (Keep the admin user)
    # 2. service (Keep your offerings)
    # 3. job_category (Keep the list of job categories)
    # 4. site_content (Keep AI data and configuration)

    # Tables to wipe (Sample/Test data)
    tables_to_wipe = [
        'lead',
        'order',
        'order_timeline',
        'notification',
        'audit_log',
        'support_ticket',
        'scheduled_email',
        'job',
        'job_subscription',
        'profile_request',
        'portfolio_item' # User might want to keep portfolio, but usually better to start fresh or re-add
    ]

    print("Cleaning sample data from local database...")
    for table in tables_to_wipe:
        try:
            # First check if table exists
            cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cur.fetchone():
                cur.execute(f"DELETE FROM \"{table}\"")
                print(f"  - Wiped {table}")
        except Exception as e:
            print(f"  - Error wiping {table}: {e}")

    # Clean non-admin users if any
    try:
        cur.execute("DELETE FROM user WHERE is_admin = 0")
        print("  - Removed all non-admin users")
    except Exception as e:
        print(f"  - Error removing users: {e}")

    conn.commit()
    conn.close()
    print("\nLocal database cleaned! Only core settings and Admin users remain.")

if __name__ == "__main__":
    clean_database()
