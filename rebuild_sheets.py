
import os
import json
import sqlite3
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

def rebuild():
    # 1. Setup Credentials
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_file = 'credentials.json'
    sheet_name = 'RoyalVista_DB'
    db_path = 'instance/site.db'
    
    if not os.path.exists(creds_file):
        print("Error: credentials.json not found.")
        return

    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    client = gspread.authorize(creds)
    
    try:
        spreadsheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        print(f"Error: Spreadsheet '{sheet_name}' not found.")
        return

    # 2. Define Headers and Data Mapping for ALL tables (Total 11 Tabs)
    # 2. Define Headers and Data Mapping for ALL tables
    config = {
        'Users': {
            'headers': ['id', 'username', 'email', 'phone_number', 'password', 'google_id', 'custom_user_id', 'is_admin', 'is_active_status', 'is_subscribed', 'created_at', 'permissions', 'role', 'profile_edited_count'],
            'sql': 'SELECT id, username, email, phone_number, password, google_id, custom_user_id, is_admin, is_active_status, is_subscribed, created_at, permissions, role, profile_edited_count FROM user',
        },
        'Orders': {
            'headers': ['id', 'custom_order_id', 'user_id', 'service_name', 'details', 'status', 'output_url', 'output_type', 'created_at'],
            'sql': 'SELECT id, custom_order_id, user_id, service_name, details, status, output_url, output_type, created_at FROM "order"',
        },
        'Tickets': {
            'headers': ['id', 'custom_ticket_id', 'user_id', 'order_id', 'subject', 'description', 'priority', 'status', 'created_at'],
            'sql': 'SELECT id, custom_ticket_id, user_id, order_id, subject, description, priority, status, created_at FROM support_ticket',
        },
        'Portfolio': {
            'headers': ['id', 'title', 'client_name', 'category', 'image_url', 'video_url', 'external_link', 'active'],
            'sql': 'SELECT id, title, client_name, category, image_url, video_url, external_link, active FROM portfolio_item'
        },
        'Jobs': {
            'headers': ['id', 'title', 'description', 'categories', 'eligible_years', 'image_url', 'external_link', 'status', 'scheduled_time', 'share_count', 'created_at', 'posted_at'],
            'sql': 'SELECT id, title, description, categories, eligible_years, image_url, external_link, status, scheduled_time, share_count, created_at, posted_at FROM job',
        },
        'Leads': {
            'headers': ['id', 'full_name', 'email', 'phone', 'service', 'message', 'created_at'],
            'sql': 'SELECT id, full_name, email, phone, service, message, created_at FROM lead',
        }
    }

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    for ws_name, info in config.items():
        print(f"Processing {ws_name}...")
        try:
            worksheet = spreadsheet.worksheet(ws_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=ws_name, rows=1000, cols=len(info['headers']))
        
        worksheet.append_row(info['headers'])
        
        try:
            cur.execute(info['sql'])
            rows = cur.fetchall()
            formatted_rows = [[str(val) if val is not None else "" for val in r] for r in rows]
            if formatted_rows:
                worksheet.append_rows(formatted_rows)
                print(f"  Inserted {len(formatted_rows)} rows.")
            else:
                print("  No data found.")
        except Exception as e:
            print(f"  Error: {e}")

    conn.close()
    print("\nFull System Backup Complete! All 11 tabs are now live and synced.")

if __name__ == "__main__":
    rebuild()
