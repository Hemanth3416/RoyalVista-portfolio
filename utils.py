from datetime import datetime
import os
import json
import sqlite3
import shutil

# Placeholder for PDF Generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
from io import BytesIO

# ... (imports are handled at module level, ensuring we don't duplicate standard library imports)
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.service_account import Credentials
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

def sync_to_google_sheets(data, category='Lead'):
    """
    Syncs form data to a Google Sheet into specific worksheets.
    Categories: Lead, Order, User, Ticket
    """
    # BETTER DATA MANAGEMENT:
    # Look for credentials in Environment Variable first (JSON string)
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDS_JSON')
    credentials_file = 'credentials.json'
    
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME', 'RoyalVista_DB')
    
    # ... (existing config)
    config = {
        'Lead': ('Leads', ['Full Name', 'Email', 'Phone', 'Service', 'Message', 'Type', 'Timestamp']),
        'Order': ('Orders', ['Order ID', 'Client Email', 'Service', 'Details', 'User ID', 'Phone', 'Status', 'Timestamp']),
        'User': ('Users', ['id', 'username', 'email', 'phone_number', 'password', 'google_id', 'custom_user_id', 'is_admin', 'is_active_status', 'is_subscribed', 'created_at', 'permissions', 'role', 'profile_edited_count']),
        'Ticket': ('Tickets', ['Ticket ID', 'User Email', 'Order ID', 'Subject', 'Priority', 'Status', 'Timestamp']),
        'Portfolio': ('Portfolio', ['ID', 'Title', 'Client', 'Category', 'Image URL', 'Status', 'Timestamp']),
        'Job': ('Jobs', ['ID', 'Title', 'Categories', 'Eligible Years', 'Status', 'Share Count', 'Timestamp']),
        'Log': ('Audit Logs', ['Log ID', 'User ID', 'Action', 'Details', 'IP', 'Timestamp']),
        'ProfileRequest': ('Profile Requests', ['ID', 'User ID', 'New Name', 'New Phone', 'Reason', 'Status', 'Timestamp']),
        'Notification': ('Notifications', ['ID', 'User ID', 'Title', 'Message', 'Status', 'Timestamp']),
        'Email': ('Emails', ['ID', 'Subject', 'Status', 'Scheduled', 'Sent At', 'Timestamp']),
        'Subscription': ('Subscriptions', ['ID', 'User ID', 'Category ID', 'Timestamp'])
    }

    if category not in config:
        print(f"Error: Unknown sync category '{category}'")
        return False

# Standardized Headers for Google Sheets Sync (Model based)
SYNC_CONFIG = {
    'User': ['id', 'username', 'email', 'phone_number', 'password', 'google_id', 'custom_user_id', 'is_admin', 'is_active_status', 'is_subscribed', 'created_at', 'permissions', 'role', 'profile_edited_count'],
    'Order': ['id', 'custom_order_id', 'user_id', 'service_name', 'details', 'status', 'output_url', 'output_type', 'created_at'],
    'Ticket': ['id', 'custom_ticket_id', 'user_id', 'order_id', 'subject', 'description', 'priority', 'status', 'created_at'],
    'Portfolio': ['id', 'title', 'client_name', 'category', 'image_url', 'video_url', 'external_link', 'active'],
    'Job': ['id', 'title', 'description', 'categories', 'eligible_years', 'image_url', 'external_link', 'status', 'scheduled_time', 'share_count', 'created_at', 'posted_at'],
    'Lead': ['id', 'full_name', 'email', 'phone', 'service', 'message', 'created_at'],
    'Notification': ['id', 'user_id', 'title', 'message', 'is_read', 'link', 'created_at'],
    'ProfileRequest': ['id', 'user_id', 'new_username', 'new_phone', 'description', 'status', 'created_at'],
    'Email': ['id', 'subject', 'body', 'recipients', 'scheduled_time', 'status', 'created_at', 'sent_at'],
    'Subscription': ['id', 'user_id', 'category_id', 'timestamp']
}

def sync_to_google_sheets(data, category='User'):
    """Synchronizes data to Google Sheets using a standardized header configuration."""
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDS_JSON')
    credentials_file = 'credentials.json'
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME', 'RoyalVista_DB')
    
    sheet_mapping = {
        'User': 'Users', 'Order': 'Orders', 'Lead': 'Leads', 'Ticket': 'Tickets',
        'Portfolio': 'Portfolio', 'Job': 'Jobs', 'ProfileRequest': 'Profile Requests',
        'Notification': 'Notifications', 'Email': 'Emails', 'Subscription': 'Subscriptions'
    }
    
    if category not in SYNC_CONFIG: return False
    ws_name = sheet_mapping.get(category, category)
    headers = SYNC_CONFIG[category]
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        if creds_json:
            import json
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

        # Duplicate Check
        unique_val = None
        col_idx = None
        if category == 'User':
            unique_val = data.get('email'); col_idx = 3
        elif data.get('id'):
            unique_val = str(data.get('id')); col_idx = 1
        
        if unique_val and col_idx:
            try:
                if str(unique_val) in worksheet.col_values(col_idx): return True
            except: pass

        worksheet.append_row(row)
        return True
    except Exception as e:
        print(f"Sheet Sync Error ({category}): {e}")
        return False

def fetch_from_google_sheets(category='User'):
    """
    Fetches data from Google Sheets for a specific category.
    Returns a list of dictionaries.
    """
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDS_JSON')
    credentials_file = 'credentials.json'
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME', 'RoyalVista_DB')
    
    config = {
        'User': 'Users',
        'Order': 'Orders',
        'Lead': 'Leads',
        'Ticket': 'Tickets',
        'Portfolio': 'Portfolio',
        'Job': 'Jobs',
        'ProfileRequest': 'Profile Requests',
        'Notification': 'Notifications'
    }
    
    if category not in config:
        return []
        
    ws_name = config[category]
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        if creds_json:
            import json
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            if not os.path.exists(credentials_file): return []
            creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
            
        client = gspread.authorize(creds)
        spreadsheet = client.open(sheet_name)
        worksheet = spreadsheet.worksheet(ws_name)
        
        # Get all records as a list of dictionaries
        return worksheet.get_all_records()
    except Exception as e:
        print(f"Error fetching from Sheets ({category}): {e}")
        return []

def send_notification_email(to_email, subject, body_html):
    """
    Sends an email using Gmail SMTP.
    Requires environment variables: MAIL_USERNAME, MAIL_PASSWORD
    """
    sender_email = os.environ.get('MAIL_USERNAME', 'royalvistatechsolutions@gmail.com')
    password = os.environ.get('MAIL_PASSWORD') # This must be the Google App Password

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
        # Use Port 587 with STARTTLS for better compatibility on Render
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls(context=context)
            server.login(sender_email, password)
            server.sendmail(sender_email, to_email, message.as_string())
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

from PIL import Image, ImageDraw, ImageFont

def apply_watermark(image_path):
    """Adds a semi-transparent rotated repeating diagonal watermark to images with gradient text."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Open and convert
        base = Image.open(image_path).convert("RGBA")
        width, height = base.size
        
        # Canvas size
        diag = int((width**2 + height**2)**0.5)
        canvas_size = int(diag * 1.5)
        
        # 1. Create the Text Mask (L mode)
        # 0 = Transparent/Black, 255 = Opaque/White
        txt_mask = Image.new("L", (canvas_size, canvas_size), 0)
        draw = ImageDraw.Draw(txt_mask)
        
        # Dynamic font size - larger for better visibility
        font_size = int(max(width, height) / 12)
        if font_size < 40: font_size = 40
        
        try:
            # Try loading a standard Serif font to match the "Sample" reference
            # Linux common paths
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
                "Times New Roman.ttf",
                "Arial.ttf" # Fallback
            ]
            font = None
            for p in font_paths:
                try:
                    font = ImageFont.truetype(p, font_size)
                    break
                except: continue
            
            if not font: font = ImageFont.load_default()
        except:
             font = ImageFont.load_default()
            
        text = "RoyalVista Tech Solutions"
        
        # Calculate text dimensions
        try:
            text_width = draw.textlength(text, font=font)
        except:
            text_width = font_size * len(text) * 0.6
            
        # Spacing - Optimized for readability
        gap_x = int(text_width * 0.6) # Tighter horizontal gap
        gap_y = int(font_size * 4)    # Reduced vertical gap for better density
        step_x = int(text_width + gap_x)
        step_y = int(font_size + gap_y)
        # Draw Text on Mask
        text_w, text_h = draw.textbbox((0, 0), text, font=font)[2:]
        margin = 20 # Denser pattern, changed from previous spacing logic
        for y in range(0, canvas_size, text_h + margin):
            for x in range(0, canvas_size, text_w + margin):
                draw.text((x, y), text, fill=255, font=font)
        
        # 2. Create Gradient Layer (Enhanced Visibility)
        # Colors: #6C63FF (108, 99, 255) -> #03dac6 (3, 218, 198)
        grad_base = Image.new("RGBA", (2, 1))
        # Increased opacity to 160 (approx 63%) for clear visibility
        grad_base.putpixel((0, 0), (108, 99, 255, 160)) 
        grad_base.putpixel((1, 0), (3, 218, 198, 160))
        
        # Resize to fill canvas (Bilinear interpolation creates the gradient)
        gradient = grad_base.resize((canvas_size, canvas_size), resample=Image.BILINEAR)
        
        # 3. Composite Gradient through Mask
        # We want the gradient ONLY where the text is
        # Create a blank transparent layer
        watermark_layer = Image.new("RGBA", (canvas_size, canvas_size), (0,0,0,0))
        # Paste gradient using text mask
        watermark_layer.paste(gradient, (0,0), txt_mask)
        
        # 4. Rotate
        rotated = watermark_layer.rotate(45, resample=Image.BICUBIC)
        
        # 5. Crop
        cx, cy = rotated.size[0] // 2, rotated.size[1] // 2
        left = cx - width // 2
        top = cy - height // 2
        final_watermark = rotated.crop((left, top, left + width, top + height))
        
        # 6. Merge
        out = Image.alpha_composite(base, final_watermark)
        
        # Save
        if image_path.lower().endswith('.png'):
            out.save(image_path, "PNG")
        else:
            out.convert("RGB").save(image_path, quality=95)
            
        return True
    except Exception as e:
        print(f"Watermark Error: {e}")
        return False

def generate_invoice_pdf(order):
    """Generates a professional PDF invoice for an order."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    p.setFont("Helvetica-Bold", 20)
    p.drawString(100, height - 80, "INVOICE - RoyalVista Tech Solutions")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 120, f"Order ID: {order.custom_order_id}")
    p.drawString(100, height - 140, f"Date: {order.created_at.strftime('%Y-%m-%d')}")
    p.drawString(100, height - 160, f"Client: {order.client.username} ({order.client.email})")
    
    p.line(100, height - 180, 500, height - 180)
    
    # Details
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, height - 210, "Project Details")
    p.setFont("Helvetica", 12)
    p.drawString(100, height - 230, f"Service: {order.service_name}")
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, height - 260, "Description:")
    p.setFont("Helvetica", 10)
    
    # Text wrapping for details
    text = p.beginText(100, height - 280)
    text.setFont("Helvetica", 10)
    lines = order.details.split('\n')
    for line in lines:
        text.textLine(line[:100]) # Simple wrap
    p.drawText(text)
    
    # Footer
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(100, 100, "Thank you for Choosing RoyalVista. For support, contact us at royalvistatechsolutions@gmail.com")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer

def log_audit(db, user_id, action, details=None, ip=None):
    from models import AuditLog, User
    # Ensure user_id is passed, else it might be NULL for system/anon actions
    log = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip)
    db.session.add(log)
    db.session.commit()
    
    # Get professional ID for sheets
    professional_id = "System"
    if user_id:
        u = User.query.get(user_id)
        if u: professional_id = u.custom_user_id

    # Sync to Sheets (Audit Log)
    sync_data = {
        'id': log.id,
        'user_id': professional_id,
        'action': action,
        'details': details,
        'ip': ip
    }
    from utils import sync_to_google_sheets
    import threading
    threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Log')).start()

def backup_db(db_path='instance/site.db', backup_dir='backups'):
    if not os.path.exists(db_path):
        return False
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    dest = os.path.join(backup_dir, filename)
    shutil.copy2(db_path, dest)
    
    # Keep only last 7 backups
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    if len(backups) > 7:
        for old in backups[:-7]:
            os.remove(os.path.join(backup_dir, old))
    return True
def upload_to_imgbb(file_path):
    """Uploads an image to ImgBB and returns the direct link."""
    api_key = os.environ.get('IMGBB_API_KEY')
    if not api_key:
        print("Error: IMGBB_API_KEY is missing in environment variables.")
        return None

    try:
        import requests
        import base64

        with open(file_path, "rb") as file:
            url = "https://api.imgbb.com/1/upload"
            payload = {
                "key": api_key,
                "image": base64.b64encode(file.read()).decode('utf-8'),
            }
            res = requests.post(url, payload)
            res.raise_for_status()
            
            data = res.json()
            # Return the direct URL of the uploaded image
            return data['data']['url']
    except Exception as e:
        print(f"ImgBB Upload Error: {e}")
        return None
