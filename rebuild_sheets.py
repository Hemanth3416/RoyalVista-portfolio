
import os
import json
import sqlite3
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Import SYNC_CONFIG from utils to be the single source of truth
try:
    from utils import SYNC_CONFIG
except ImportError:
    # Fallback if utils.py import fails during direct execution
    SYNC_CONFIG = {
        'User': ['id', 'username', 'email', 'phone_number', 'password', 'google_id', 'custom_user_id', 'is_admin', 'is_active_status', 'is_subscribed', 'created_at', 'permissions', 'role', 'profile_edited_count'],
        'Service': ['id', 'title', 'description', 'icon_class', 'active'],
        'Portfolio': ['id', 'title', 'client_name', 'category', 'image_url', 'video_url', 'external_link', 'active'],
        'Job': ['id', 'title', 'description', 'categories', 'eligible_years', 'image_url', 'external_link', 'status', 'scheduled_time', 'share_count', 'created_at', 'posted_at'],
        'JobCategory': ['id', 'name'],
        'Order': ['id', 'custom_order_id', 'user_id', 'service_id', 'service_name', 'details', 'status', 'output_url', 'output_type', 'created_at'],
        'Ticket': ['id', 'custom_ticket_id', 'user_id', 'order_id', 'subject', 'description', 'priority', 'status', 'created_at'],
        'Lead': ['id', 'full_name', 'email', 'phone', 'service', 'message', 'created_at'],
        'Log': ['id', 'user_id', 'action', 'details', 'ip_address', 'timestamp'],
        'Subscription': ['id', 'user_id', 'category_id'],
        'Timeline': ['id', 'order_id', 'action_type', 'performed_by', 'timestamp', 'note', 'file_url', 'file_type'],
        'SiteContent': ['key', 'value']
    }

SHEET_MAPPING = {
    'User': 'Users', 'Order': 'Orders', 'Lead': 'Leads', 'Ticket': 'Tickets',
    'Portfolio': 'Portfolio', 'Job': 'Jobs', 'ProfileRequest': 'Profile Requests',
    'Notification': 'Notifications', 'Email': 'Emails', 'Subscription': 'Subscriptions',
    'Service': 'Services', 'JobCategory': 'Job Categories', 'Log': 'Audit Logs',
    'Timeline': 'Order Timelines', 'SiteContent': 'Site Content'
}

SQL_MAPPING = {
    'User': 'user',
    'Service': 'service',
    'Portfolio': 'portfolio_item',
    'Job': 'job',
    'JobCategory': 'job_category',
    'Order': '"order"',
    'Ticket': 'support_ticket',
    'Lead': 'lead',
    'Log': 'audit_log',
    'Subscription': 'job_subscription',
    'Timeline': 'order_timeline',
    'SiteContent': 'site_content'
}

def rebuild():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_file = 'credentials.json'
    sheet_name = 'RoyalVista_DB'
    
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
        
    for category, ws_name in SHEET_MAPPING.items():
        if category not in SYNC_CONFIG: continue
        headers = SYNC_CONFIG[category]
        
        print(f"Resetting sheet: {ws_name}...")
        try:
            # Try to get the worksheet
            worksheet = spreadsheet.worksheet(ws_name)
            # Delete it
            spreadsheet.del_worksheet(worksheet)
            print(f"  Deleted existing '{ws_name}'")
        except gspread.WorksheetNotFound:
            pass
            
        # Create fresh
        worksheet = spreadsheet.add_worksheet(title=ws_name, rows=1000, cols=len(headers) + 2)
        worksheet.append_row(headers)
        print(f"  Created '{ws_name}' with headers: {headers}")

    print("\nComplete! All sheets have been wiped and re-initialized with correct headers.")

if __name__ == "__main__":
    rebuild()
