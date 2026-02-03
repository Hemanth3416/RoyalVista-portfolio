
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
    config = {
        'Leads': {
            'headers': ['Full Name', 'Email', 'Phone', 'Service', 'Message', 'Type', 'Timestamp'],
            'sql': 'SELECT full_name, email, phone, service, message, "Lead", created_at FROM lead',
        },
        'Orders': {
            'headers': ['Order ID', 'Client Email', 'Service', 'Details', 'User ID', 'Phone', 'Status', 'Timestamp'],
            'sql': 'SELECT o.custom_order_id, u.email, o.service_name, o.details, u.custom_user_id, u.phone_number, o.status, o.created_at FROM "order" o JOIN user u ON o.user_id = u.id',
        },
        'Users': {
            'headers': ['id', 'username', 'email', 'phone_number', 'password', 'google_id', 'custom_user_id', 'is_admin', 'is_active_status', 'is_subscribed', 'created_at', 'permissions', 'role', 'profile_edited_count'],
            'sql': 'SELECT id, username, email, phone_number, password, google_id, custom_user_id, is_admin, is_active_status, is_subscribed, created_at, permissions, role, profile_edited_count FROM user',
        },
        'Tickets': {
            'headers': ['Ticket ID', 'User Email', 'Order ID', 'Subject', 'Priority', 'Status', 'Timestamp'],
            'sql': 'SELECT t.custom_ticket_id, u.email, o.custom_order_id, t.subject, t.priority, t.status, t.created_at FROM support_ticket t JOIN user u ON t.user_id = u.id LEFT JOIN "order" o ON t.order_id = o.id',
        },
        'Portfolio': {
            'headers': ['ID', 'Title', 'Client', 'Category', 'Image URL', 'Status', 'Timestamp'],
            'sql': 'SELECT id, title, client_name, category, image_url, active, "" FROM portfolio_item'
        },
        'Jobs': {
            'headers': ['ID', 'Title', 'Categories', 'Eligible Years', 'Status', 'Share Count', 'Timestamp'],
            'sql': 'SELECT id, title, categories, eligible_years, status, share_count, created_at FROM job',
        },
        'Audit Logs': {
            'headers': ['Log ID', 'User ID', 'Action', 'Details', 'IP', 'Timestamp'],
            'sql': 'SELECT l.id, u.custom_user_id, l.action, l.details, l.ip_address, l.timestamp FROM audit_log l LEFT JOIN user u ON l.user_id = u.id',
        },
        'Profile Requests': {
            'headers': ['ID', 'User ID', 'New Name', 'New Phone', 'Reason', 'Status', 'Timestamp'],
            'sql': 'SELECT p.id, u.custom_user_id, p.new_username, p.new_phone, p.description, p.status, p.created_at FROM profile_request p JOIN user u ON p.user_id = u.id',
        },
        'Notifications': {
            'headers': ['ID', 'User ID', 'Title', 'Message', 'Status', 'Timestamp'],
            'sql': 'SELECT n.id, u.custom_user_id, n.title, n.message, n.is_read, n.created_at FROM notification n JOIN user u ON n.user_id = u.id',
        },
        'Emails': {
            'headers': ['ID', 'Subject', 'Status', 'Scheduled At', 'Sent At', 'Timestamp'],
            'sql': 'SELECT id, subject, status, scheduled_time, sent_at, created_at FROM scheduled_email',
        },
        'Subscriptions': {
            'headers': ['ID', 'User ID', 'Category ID', 'Timestamp'],
            'sql': 'SELECT s.id, u.custom_user_id, s.category_id, s.id FROM job_subscription s JOIN user u ON s.user_id = u.id',
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
