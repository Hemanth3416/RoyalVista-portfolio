from datetime import datetime
import os
import json
import sqlite3
import shutil
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import BytesIO

# Placeholder and Optional Imports
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.service_account import Credentials
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Standardized Headers for Google Sheets Sync (Model based)
SYNC_CONFIG = {
    'User': ['id', 'username', 'email', 'phone_number', 'password', 'google_id', 'custom_user_id', 'is_admin', 'is_active_status', 'is_subscribed', 'created_at', 'permissions', 'role', 'profile_edited_count'],
    'Service': ['id', 'title', 'description', 'icon_class', 'active'],
    'Portfolio': ['ID', 'Title', 'Client', 'Category', 'Image URL', 'Status', 'Timestamp'],
    'Job': ['ID', 'Title', 'Categories', 'Eligible Years', 'Status', 'Share Count', 'Timestamp'],
    'JobCategory': ['id', 'name'],
    'Order': ['Order ID', 'Client Email', 'Service', 'Details', 'User ID', 'Phone', 'Status', 'Timestamp'],
    'Ticket': ['Ticket ID', 'User Email', 'Order ID', 'Subject', 'Priority', 'Status', 'Timestamp'],
    'Lead': ['Full Name', 'Email', 'Phone', 'Service', 'Message', 'Type', 'Timestamp'],
    'Notification': ['ID', 'User ID', 'Title', 'Message', 'Status', 'Timestamp'],
    'ProfileRequest': ['ID', 'User ID', 'New Name', 'New Phone', 'Reason', 'Status', 'Timestamp'],
    'Log': ['Log ID', 'User ID', 'Action', 'Details', 'IP', 'Timestamp'],
    'Email': ['ID', 'Subject', 'Status', 'Scheduled At', 'Sent At', 'Timestamp'],
    'Subscription': ['ID', 'User ID', 'Category ID', 'Timestamp'],
    'Timeline': ['id', 'order_id', 'action_type', 'performed_by', 'timestamp', 'note', 'file_url', 'file_type'],
    'SiteContent': ['key', 'value']
}

def sync_to_google_sheets(data, category='User'):
    """Synchronizes data to Google Sheets using a standardized header configuration."""
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDS_JSON')
    credentials_file = 'credentials.json'
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME', 'RoyalVista_DB')
    
    sheet_mapping = {
        'User': 'Users', 'Order': 'Orders', 'Lead': 'Leads', 'Ticket': 'Tickets',
        'Portfolio': 'Portfolio', 'Job': 'Jobs', 'ProfileRequest': 'Profile Requests',
        'Notification': 'Notifications', 'Email': 'Emails', 'Subscription': 'Subscriptions',
        'Service': 'Services', 'JobCategory': 'Job Categories', 'Log': 'Audit Logs',
        'Timeline': 'Order Timelines', 'SiteContent': 'Site Content'
    }
    
    if category not in SYNC_CONFIG: 
        print(f"Sync error: Unconfigured category '{category}'")
        return False

    ws_name = sheet_mapping.get(category, category)
    headers = SYNC_CONFIG[category]
    timestamp = datetime.utcnow().isoformat()

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        if creds_json:
            creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
        else:
            if not os.path.exists(credentials_file): return False
            creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
            
        client = gspread.authorize(creds)
        spreadsheet = client.open(sheet_name)
        
        try:
            worksheet = spreadsheet.worksheet(ws_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=ws_name, rows=1000, cols=len(headers) + 2)
            worksheet.append_row(headers)

        # Build Row
        row = []
        for h in headers:
            val = data.get(h)
            if val is None and h in ['created_at', 'timestamp']: val = timestamp
            row.append(str(val) if val is not None else "")

        # Duplicate Check (Avoid identical row spam)
        # For sensitive categories like User, check specific column
        unique_val = None
        col_idx = None
        if category == 'User':
            unique_val = data.get('email'); col_idx = 3 # column C
        elif category in ['Order', 'Ticket', 'Portfolio', 'Job', 'Service', 'JobCategory', 'SiteContent', 'Log']:
            # Use the first column if it's an ID or 'key'
            unique_val = str(data.get(headers[0]))
            col_idx = 1
        
        if unique_val and col_idx:
            try:
                # Limit check to last 100 rows for performance
                vals = worksheet.col_values(col_idx)
                if str(unique_val) in vals:
                    # Update existing row logic would go here, currently we just skip
                    return True
            except: pass

        worksheet.append_row(row)
        return True
    except Exception as e:
        print(f"Sheet Sync Error ({category}): {e}")
        return False

def fetch_from_google_sheets(category='User'):
    """Fetches data from Google Sheets for a specific category."""
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDS_JSON')
    credentials_file = 'credentials.json'
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME', 'RoyalVista_DB')
    
    sheet_mapping = {
        'User': 'Users', 'Order': 'Orders', 'Lead': 'Leads', 'Ticket': 'Tickets',
        'Portfolio': 'Portfolio', 'Job': 'Jobs', 'ProfileRequest': 'Profile Requests',
        'Notification': 'Notifications', 'Email': 'Emails', 'Subscription': 'Subscriptions',
        'Service': 'Services', 'JobCategory': 'Job Categories', 'Log': 'Audit Logs',
        'Timeline': 'Order Timelines', 'SiteContent': 'Site Content'
    }
    
    if category not in sheet_mapping:
        return []
        
    ws_name = sheet_mapping[category]
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        if creds_json:
            creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
        else:
            if not os.path.exists(credentials_file): return []
            creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
            
        client = gspread.authorize(creds)
        spreadsheet = client.open(sheet_name)
        worksheet = spreadsheet.worksheet(ws_name)
        
        return worksheet.get_all_records()
    except Exception as e:
        print(f"Error fetching from Sheets ({category}): {e}")
        return []

def send_notification_email(to_email, subject, body_html):
    """Sends an email using Gmail SMTP."""
    sender_email = os.environ.get('MAIL_USERNAME', 'royalvistatechsolutions@gmail.com')
    password = os.environ.get('MAIL_PASSWORD')

    if not password:
        print(f"[MOCK EMAIL] To: {to_email} | Subject: {subject}")
        return False

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body_html, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls(context=context)
            server.login(sender_email, password)
            server.sendmail(sender_email, to_email, message.as_string())
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

def log_audit(db, user_id, action, details=None, ip=None):
    from models import AuditLog, User
    log = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip)
    db.session.add(log)
    db.session.commit()
    
    prof_id = "System"
    if user_id:
        u = User.query.get(user_id)
        if u: prof_id = u.custom_user_id

    sync_data = {
        'Log ID': log.id,
        'User ID': prof_id,
        'Action': action,
        'Details': details,
        'IP': ip,
        'Timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }
    import threading
    threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Log')).start()

def apply_watermark(image_path):
    """Adds a semi-transparent rotated repeating diagonal watermark to images."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        base = Image.open(image_path).convert("RGBA")
        width, height = base.size
        diag = int((width**2 + height**2)**0.5)
        canvas_size = int(diag * 1.5)
        
        txt_mask = Image.new("L", (canvas_size, canvas_size), 0)
        draw = ImageDraw.Draw(txt_mask)
        font_size = int(max(width, height) / 12)
        if font_size < 40: font_size = 40
        
        # Load font
        font = None
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "Arial.ttf"]:
            try:
                font = ImageFont.truetype(p, font_size)
                break
            except: continue
        if not font: font = ImageFont.load_default()
            
        text = "RoyalVista Tech Solutions"
        text_w, text_h = draw.textbbox((0, 0), text, font=font)[2:]
        margin = 40
        for y in range(0, canvas_size, text_h + margin):
            for x in range(0, canvas_size, text_w + margin):
                draw.text((x, y), text, fill=255, font=font)
        
        grad_base = Image.new("RGBA", (2, 1))
        grad_base.putpixel((0, 0), (108, 99, 255, 140)) 
        grad_base.putpixel((1, 0), (3, 218, 198, 140))
        gradient = grad_base.resize((canvas_size, canvas_size), resample=Image.BILINEAR)
        
        watermark_layer = Image.new("RGBA", (canvas_size, canvas_size), (0,0,0,0))
        watermark_layer.paste(gradient, (0,0), txt_mask)
        rotated = watermark_layer.rotate(45, resample=Image.BICUBIC)
        
        cx, cy = rotated.size[0] // 2, rotated.size[1] // 2
        final_watermark = rotated.crop((cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2))
        out = Image.alpha_composite(base, final_watermark)
        
        if image_path.lower().endswith('.png'):
            out.save(image_path, "PNG")
        else:
            out.convert("RGB").save(image_path, quality=95)
        return True
    except Exception as e:
        print(f"Watermark Error: {e}")
        return False

def generate_invoice_pdf(order):
    if not REPORTLAB_AVAILABLE: return None
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    p.setFont("Helvetica-Bold", 18)
    p.drawString(100, h - 80, "INVOICE - RoyalVista Tech Solutions")
    p.setFont("Helvetica", 12)
    p.drawString(100, h - 120, f"Order ID: {order.custom_order_id}")
    p.drawString(100, h - 140, f"Date: {order.created_at.strftime('%Y-%m-%d')}")
    p.drawString(100, h - 160, f"Client: {order.client.username} ({order.client.email})")
    p.line(100, h - 180, 500, h - 180)
    p.drawString(100, h - 210, f"Service: {order.service_name}")
    p.drawString(100, h - 230, "Details:")
    text = p.beginText(100, h - 250)
    text.setFont("Helvetica", 10)
    for line in order.details.split('\n'):
        text.textLine(line[:100])
    p.drawText(text)
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def upload_to_imgbb(file_path):
    api_key = os.environ.get('IMGBB_API_KEY')
    if not api_key: return None
    try:
        import requests, base64
        with open(file_path, "rb") as file:
            url = "https://api.imgbb.com/1/upload"
            payload = {"key": api_key, "image": base64.b64encode(file.read()).decode('utf-8')}
            res = requests.post(url, payload)
            return res.json()['data']['url']
    except Exception as e:
        print(f"ImgBB Error: {e}")
        return None

def backup_db(db_path='instance/site.db', backup_dir='backups'):
    if not os.path.exists(db_path): return False
    if not os.path.exists(backup_dir): os.makedirs(backup_dir)
    dest = os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(db_path, dest)
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    if len(backups) > 7:
        for old in backups[:-7]: os.remove(os.path.join(backup_dir, old))
    return True
