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

    ws_name, headers = config[category]
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not creds_json and not os.path.exists(credentials_file):
        print(f"[MOCK SYNC] {category} Data: {data}")
        return False
        
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        if creds_json:
            import json
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
            
        client = gspread.authorize(creds)
        
        try:
            spreadsheet = client.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            print(f"Error: Spreadsheet '{sheet_name}' not found.")
            return False

        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(ws_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=ws_name, rows=100, cols=len(headers))
            worksheet.append_row(headers)

        # Prepare row data based on category
        row = []
        if category == 'Lead':
            row = [data.get('full_name'), data.get('email'), data.get('phone'), data.get('service'), data.get('message'), 'Lead', timestamp]
        elif category == 'Order':
            row = [data.get('order_id'), data.get('user'), data.get('service'), data.get('details'), data.get('user_id'), data.get('phone'), data.get('status', 'Submitted'), timestamp]
        elif category == 'User':
            row = [
                data.get('id'),
                data.get('username'),
                data.get('email'),
                data.get('phone_number'),
                data.get('password'),
                data.get('google_id'),
                data.get('custom_user_id'),
                data.get('is_admin'),
                data.get('is_active_status'),
                data.get('is_subscribed'),
                data.get('created_at', timestamp),
                data.get('permissions'),
                data.get('role'),
                data.get('profile_edited_count')
            ]
        elif category == 'Ticket':
            row = [data.get('ticket_id'), data.get('user'), data.get('order_id'), data.get('subject'), data.get('priority'), data.get('status', 'Open'), timestamp]
        elif category == 'Portfolio':
            row = [data.get('id'), data.get('title'), data.get('client_name'), data.get('category'), data.get('image_url'), data.get('active'), timestamp]
        elif category == 'Job':
            row = [data.get('id'), data.get('title'), data.get('categories'), data.get('eligible_years'), data.get('status'), data.get('share_count'), timestamp]
        elif category == 'Log':
            row = [data.get('id'), data.get('user_id'), data.get('action'), data.get('details'), data.get('ip'), timestamp]
        elif category == 'ProfileRequest':
            row = [data.get('id'), data.get('user_id'), data.get('new_name'), data.get('new_phone'), data.get('description'), data.get('status'), timestamp]
        elif category == 'Notification':
            row = [data.get('id'), data.get('user_id'), data.get('title'), data.get('message'), data.get('is_read'), timestamp]
        elif category == 'Email':
            row = [data.get('id'), data.get('subject'), data.get('status'), data.get('scheduled'), data.get('sent_at'), timestamp]
        elif category == 'Subscription':
            row = [data.get('id'), data.get('user_id'), data.get('category_id'), timestamp]

        # Check for duplicates before appending
        data_col_index = None
        unique_val = None
        
        if category == 'User':
            data_col_index = 3 # Email is 3rd column (id, username, email)
            unique_val = data.get('email')
        # Allow duplicate Leads (same email can contact multiple times)
        # elif category == 'Lead': ...  REMOVED
        elif category == 'Order':
            data_col_index = 1 # Order ID is 1st column
            unique_val = data.get('order_id')
        elif category == 'Ticket':
            data_col_index = 1 # Ticket ID is 1st column
            unique_val = data.get('ticket_id')

        if data_col_index and unique_val:
            try:
                # Get all values in the unique column
                existing_vals = worksheet.col_values(data_col_index)
                if unique_val in existing_vals:
                    print(f"Skipping sync for {category}: {unique_val} already exists in Sheet.")
                    return True # Treat as success to avoid retries
            except Exception as e:
                print(f"Error checking duplicates in Sheet: {e}")

        worksheet.append_row(row)
        return True

    except Exception as e:
        print(f"Google Sheets Sync Error ({category}): {e}")
        # Local Fallback
        try:
            with open('local_sync_log.csv', 'a') as f:
                f.write(f"{timestamp},{category},{json.dumps(data)}\n")
        except: pass
        return False

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
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
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
        
        # Dynamic font size - Serif fonts tend to be thinner, so maybe slightly larger or same
        font_size = int(max(width, height) / 30)
        if font_size < 20: font_size = 20
        
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
            
        # Spacing - The sample has significant spacing
        gap_x = int(text_width * 0.8) # Wider gap between words
        gap_y = int(font_size * 6)    # Significant vertical gap
        step_x = int(text_width + gap_x)
        step_y = int(font_size + gap_y)
        
        # Draw Text on Mask
        for y in range(0, canvas_size, step_y):
            row_idx = y // step_y
            # Offset every other row heavily to create the diagonal checkerboard feel
            offset_x = int(step_x / 2) if row_idx % 2 == 1 else 0
            
            for x in range(-int(step_x), canvas_size, step_x):
                # Draw white text (full opacity on mask)
                draw.text((x + offset_x, y), text, font=font, fill=255)
        
        # 2. Create Gradient Layer (Lightly applied)
        # Colors: #6C63FF (108, 99, 255) -> #03dac6 (3, 218, 198)
        grad_base = Image.new("RGBA", (2, 1))
        # Very low opacity (30) -> Adjusted to 60 (approx 23%) for better visibility while still being "lightly"
        grad_base.putpixel((0, 0), (108, 99, 255, 60)) 
        grad_base.putpixel((1, 0), (3, 218, 198, 60))
        
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
