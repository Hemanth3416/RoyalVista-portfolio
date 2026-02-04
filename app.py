from flask import Flask, render_template, url_for, flash, redirect, request, send_file, session, jsonify
import os
from werkzeug.middleware.proxy_fix import ProxyFix
import re
import secrets
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass
import random
import string
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from models import db, User, Service, Order, SiteContent, OrderTimeline, PortfolioItem, Notification, AuditLog, SupportTicket, Job, JobCategory, JobSubscription, Lead, ProfileRequest
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from utils import generate_invoice_pdf, sync_to_google_sheets, send_notification_email, log_audit, backup_db, apply_watermark
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import json
import threading
from models import ScheduledEmail

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests

# Google OAuth Config
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# AI Engine Initialization
from ai_engine import RoyalVistaAI
chatbot_data_path = os.path.join(os.path.dirname(__file__), 'chatbot_data.json')
rv_ai = RoyalVistaAI(chatbot_data_path)

# Check for environment variable, fallback to dev key if not set
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_royalvista_key_2026')
csrf = CSRFProtect(app)

@app.route("/healthz")
def healthz():
    return "OK", 200

# BETTER DATA MANAGEMENT:
# If DATABASE_URL is set (Cloud SQL), use it. Otherwise, use local SQLite.
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'assets', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Email Scheduler Configuration
# Process scheduled tasks (emails and jobs)
def process_scheduled_tasks():
    with app.app_context():
        # Process Emails
        pending_emails = ScheduledEmail.query.filter(
            ScheduledEmail.status == 'Scheduled',
            ScheduledEmail.scheduled_time <= datetime.utcnow()
        ).all()
        
        for email in pending_emails:
            try:
                recipients = json.loads(email.recipients)
                for addr in recipients:
                    send_email_styled(addr, email.subject, 'emails/newsletter.html', 
                                         subject=email.subject, body=email.body)
                
                email.status = 'Sent'
                email.sent_at = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                email.status = 'Failed'
                email.error_log = str(e)
                db.session.commit()

        # Process Scheduled Jobs
        pending_jobs = Job.query.filter(
            Job.status == 'Scheduled',
            Job.scheduled_time <= datetime.utcnow()
        ).all()
        
        for job in pending_jobs:
            job.status = 'Posted'
            job.posted_at = datetime.utcnow()
            db.session.commit()
            
            # Notify subscribers
            notify_job_subscribers(job)

def notify_job_subscribers(job):
    from models import JobSubscription, User, JobCategory
    if not job.categories: return
    cat_names = [c.strip() for c in job.categories.split(';') if c.strip()]
    # Get user IDs subscribed to any of these categories
    sub_query = db.session.query(User.email).join(JobSubscription).join(JobCategory).filter(JobCategory.name.in_(cat_names)).distinct().all()
    recipient_emails = [r[0] for r in sub_query]
    
    for email in recipient_emails:
        send_email_styled(
            email, 
            f"New Job Alert: {job.title}", 
            'emails/job_alert.html',
            job_title=job.title,
            categories=job.categories.replace(';', ', '),
            eligible_years=job.eligible_years.replace(';', ', '),
            image_url=url_for('static', filename=job.image_url, _external=True) if job.image_url else None,
            description=job.description,
            detail_url=url_for('job_detail', job_id=job.id, _external=True),
            unsubscribe_link=url_for('job_subscribe', _external=True)
        )

# Initialize Scheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Kolkata'))
scheduler.add_job(func=process_scheduled_tasks, trigger="interval", minutes=1)
scheduler.start()

def validate_inputs(*args):
    """Checks if any provided input is empty or whitespace only."""
    for arg in args:
        if not arg or not str(arg).strip():
            return False
    return True

def validate_phone_format(phone):
    """Checks if phone number contains only digits and optional leading +."""
    if not phone: return False
    # Allow + at start, then digits. Length 7-15.
    pattern = r'^\+?[0-9]{7,15}$'
    return bool(re.match(pattern, phone))

def gen_order_id():
    chars = string.ascii_uppercase + string.digits
    return 'RVTS' + ''.join(random.choice(chars) for _ in range(8))

def gen_ticket_id():
    # Simple sequential-like or just random unique for RoyalVista branding
    rand = ''.join(random.choice(string.digits) for _ in range(4))
    return f"RVTSTICKET{rand}"

def gen_user_id():
    rand = ''.join(random.choice(string.digits) for _ in range(6))
    return f"RVTSUSER{rand}"

def send_email_styled(to_email, subject, template, **kwargs):
    """Renders an HTML email template and sends it."""
    with app.app_context():
        try:
            body_html = render_template(template, **kwargs)
            return send_notification_email(to_email, subject, body_html)
        except Exception as e:
            print(f"Template Error in send_email_styled: {e}")
            return False

def add_notification(user_id, title, message, link=None, template=None, email_subject=None, **template_kwargs):
    """Adds a DB notification and optionally sends a styled email."""
    notif = Notification(user_id=user_id, title=title, message=message, link=link)
    db.session.add(notif)
    db.session.commit()
    
    user = User.query.get(user_id)
    # Sync to Sheets
    sync_data = {
        'id': notif.id,
        'user_id': user.custom_user_id if user else "Unknown",
        'title': title,
        'message': message,
        'is_read': notif.is_read
    }
    threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Notification')).start()
    if user:
        if template:
            # Send styled email if template provided
            subj = email_subject if email_subject else f"RoyalVista Alert: {title}"
            template_kwargs.setdefault('user_name', user.username)
            send_email_styled(user.email, subj, template, **template_kwargs)
        else:
            # Fallback to simple email if no template
            body = f"<h2>{title}</h2><p>{message}</p><a href='{link if link else '#'}'>View Details</a>"
            send_notification_email(user.email, f"RoyalVista Alert: {title}", body)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_db():
    with app.app_context():
        # Ensure instance folder exists
        if not os.path.exists('instance'):
            os.makedirs('instance')
        
        # Using a safer approach for schema updates
        db.create_all()
        
        # Manual migration for missing columns
        for col, dtype in [("is_subscribed", "BOOLEAN DEFAULT 1"), ("created_at", "DATETIME"), ("permissions", "TEXT"), ("role", "VARCHAR(20) DEFAULT 'Client'"), ("is_active_status", "BOOLEAN DEFAULT 1"), ("profile_edited_count", "INTEGER DEFAULT 0"), ("custom_user_id", "VARCHAR(20)")]:
            try:
                db.session.execute(db.text(f"ALTER TABLE user ADD COLUMN {col} {dtype}"))
                db.session.commit()
            except Exception:
                db.session.rollback()

        # Update existing users without a Custom ID (using raw SQL to avoid model mismatch)
        try:
            users_without_id = db.session.execute(db.text("SELECT id FROM user WHERE custom_user_id IS NULL")).fetchall()
            for row in users_without_id:
                new_id = gen_user_id()
                db.session.execute(db.text("UPDATE user SET custom_user_id = :cid WHERE id = :uid"), 
                                   {'cid': new_id, 'uid': row[0]})
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"ID Update Error: {e}")
        
        if not User.query.filter_by(is_admin=True).first():
            hashed_pw = bcrypt.generate_password_hash('RoyalVista@2026').decode('utf-8')
            # Super Admin
            admin = User(username='RoyalVista Admin', email='royalvistatechsolutions@gmail.com', password=hashed_pw, is_admin=True, role='Super Admin', permissions=json.dumps(['jobs', 'newsletters', 'chatbot', 'users']), phone_number="+1234567890")
            db.session.add(admin)
        
        if not Service.query.first():
            db.session.add_all([
                Service(title='Web Design', description='Professional & responsive.', icon_class='fas fa-desktop'),
                Service(title='Logo Design', description='Brand identity experts.', icon_class='fas fa-pen-nib'),
                Service(title='Video Editing', description='High-quality cuts.', icon_class='fas fa-video'),
                Service(title='Thumbnails', description='Click-worthy designs.', icon_class='fas fa-image'),
                Service(title='Posters & Ads', description='Impactful visuals.', icon_class='fas fa-ad'),
                Service(title='Wedding Invitations', description='Elegant & memorable designs.', icon_class='fas fa-heart'),
                Service(title='SEO Services', description='Boost your online visibility.', icon_class='fas fa-search'),
                Service(title='Social Media Marketing', description='Grow your brand presence.', icon_class='fas fa-share-alt'),
                Service(title='Others', description='Custom services tailored to your needs.', icon_class='fas fa-ellipsis-h')
            ])
            
        if not SiteContent.query.get('hero_title'):
            db.session.add_all([
                SiteContent(key='hero_title', value='RoyalVista Tech Solutions<br>Empowering Brands with <span class="highlight">Innovation</span>'),
                SiteContent(key='hero_subtitle', value='Premium Web Design, Logo Identity, and Video Solutions.'),
                SiteContent(key='about_title', value='About <span class="highlight">RoyalVista</span>'),
                SiteContent(key='about_text', value='We are a dedicated team of digital creators specializing in building strong online identities for businesses and professionals globally.'),
                SiteContent(key='contact_heading', value='Grow Your <span class="highlight">Digital Presence</span>')
            ])

        # Default Job Categories
        from models import JobCategory
        if not JobCategory.query.first():
            db.session.add_all([
                JobCategory(name='2024'),
                JobCategory(name='2025'),
                JobCategory(name='2026'),
                JobCategory(name='Fresher'),
                JobCategory(name='Experienced'),
                JobCategory(name='Hackathons')
            ])
            
        db.session.commit()

# --- Decorators & Helpers ---
from functools import wraps
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin:
                return redirect(url_for('login'))
            
            # Super Admin has all permissions
            if current_user.role == 'Super Admin':
                return f(*args, **kwargs)
                
            perms = json.loads(current_user.permissions or '[]')
            if permission not in perms:
                flash(f"You don't have permission to access {permission}.", 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Context Processors ---
@app.context_processor
def inject_global_data():
    notifs = []
    unread_count = 0
    if current_user.is_authenticated:
        notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    from models import JobCategory
    all_cats = JobCategory.query.all()
    return dict(header_notifications=notifs, unread_count=unread_count, all_job_categories=all_cats, json=json)

# --- Routes ---

@app.route("/")
def home():
    services = Service.query.filter_by(active=True).all()
    portfolio = PortfolioItem.query.filter_by(active=True).all()
    content = {item.key: item.value for item in SiteContent.query.all()}
    return render_template('index.html', services=services, portfolio=portfolio, content=content)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    
    # Pre-fill from session (if coming from Google Login)
    prefill_username = session.pop('prefill_username', None)
    prefill_email = session.pop('prefill_email', None)

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        print(f"DEBUG: Registration POST received. Name: {username}, Email: {email}, Phone: {phone}")
        
        if not validate_inputs(username, email, password):
            print(f"DEBUG: Validation Failed for {email}")
            flash('Please fill in all required fields.', 'danger')
            return render_template('login.html', mode='register', username=username, email=email, phone=phone)
            
        if phone and not validate_phone_format(phone):
            flash('Invalid phone number. Use only digits and optional leading + (7-15 digits)', 'danger')
            return render_template('login.html', mode='register', username=username, email=email, phone=phone)
        
        # Check for duplicates: Email OR Phone
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            print(f"DEBUG: Email {email} already registered.")
            flash('This email is already registered. Please login.', 'warning')
            return render_template('login.html', mode='login', email=email)

        if phone:
            existing_phone = User.query.filter_by(phone_number=phone).first()
            if existing_phone:
                print(f"DEBUG: Phone {phone} already registered.")
                flash('This phone number is already linked to an account. Please login.', 'warning')
                return render_template('login.html', mode='register', username=username, email=email, phone=phone)
        
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        
        try:
            # Check for Super Admin Email
            role = 'Client'
            is_admin = False
            perms = '[]'
            if email == 'royalvistatechsolutions@gmail.com':
                role = 'Super Admin'
                is_admin = True
                perms = json.dumps(['jobs', 'newsletters', 'chatbot', 'users'])
                
            user = User(username=username, email=email, phone_number=phone, password=hashed_pw, 
                        role=role, is_admin=is_admin, permissions=perms, custom_user_id=gen_user_id())
            db.session.add(user)
            db.session.commit()
            print(f"DEBUG: User {user.id} created successfully.")
            
            # Background Sync to Sheets (to avoid blocking the request)
            sync_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'password': user.password,
                'google_id': user.google_id,
                'custom_user_id': user.custom_user_id,
                'is_admin': user.is_admin,
                'is_active_status': user.is_active_status,
                'is_subscribed': user.is_subscribed,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'permissions': user.permissions,
                'role': user.role,
                'profile_edited_count': user.profile_edited_count
            }
            threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'User')).start()
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG: Registration Storage Error: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('login.html', mode='register', username=username, email=email, phone=phone)

        # Audit & Notification
        log_audit(db, user.id, "User Registered", f"Email: {email}")
        add_notification(user.id, "Welcome to RoyalVista!", 
                         "Explore our services and start your first project today.", 
                         link=url_for('dashboard'), 
                         template='emails/welcome.html')
        
        # Notify Admin
        admin = User.query.filter_by(is_admin=True).first()
        if admin:
            add_notification(admin.id, "New User Registration", f"User {username} ({user.custom_user_id}) just signed up.", 
                             link=url_for('dashboard'),
                             template='emails/admin_alert.html', 
                             event_type='New User', 
                             event_details=f"User ID: {user.custom_user_id} | Name: {username} joined.", 
                             user_name='Admin', user_email=email)

        login_user(user)
        flash('Welcome to RoyalVista!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', mode='register', username=prefill_username, email=prefill_email)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check password
            if bcrypt.check_password_hash(user.password, password):
                login_user(user)
                log_audit(db, user.id, "User Login")
                # Redirect clients directly to Pipeline tab, admins to default view
                anchor = 'tab-pipeline' if user.role == 'Client' else None
                return redirect(url_for('dashboard', _anchor=anchor))
            else:
                # Password incorrect. Check if this is a Google-only account trying to login manually.
                # Note: Google users get a random password on creation, so manual login is impossible unless they reset it.
                if user.google_id and not user.password: 
                    # This case handles if we ever allow null passwords, though currently we set random ones.
                    flash('This account was created with Google. Please use "Login with Google".', 'warning')
                elif user.google_id:
                     flash('Invalid credentials. If you signed up with Google, please use that button or reset your password.', 'danger')
                else:
                    flash('Invalid credentials.', 'danger')
        else:
            flash('Invalid credentials.', 'danger')
            
    return render_template('login.html', mode='login')

from urllib.parse import urlparse

@app.route("/login/google")
def google_login():
    # If redirect_uri is not set in environment, we use a dynamic fallback
    redirect_uri = GOOGLE_REDIRECT_URI or url_for('google_callback', _external=True)

    mode = request.args.get('mode', 'login')
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)
    session.permanent = True
    session['oauth_state'] = state
    session['oauth_mode'] = mode
    
    print(f"DEBUG: Google Login. Mode: {mode}, State: {state}")
    
    # Build Google OAuth URL
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        "response_type=code&"
        "scope=openid%20email%20profile&"
        f"state={state}&"
        "access_type=offline&"
        "prompt=consent"
    )
    
    return redirect(google_auth_url)

@app.route("/auth/google/callback")
def google_callback():
    # Verify state to prevent CSRF
    state = request.args.get('state')
    stored_state = session.get('oauth_state')
    
    print(f"DEBUG: Callback. State: {state}, Stored: {stored_state}")
    
    if not state or state != stored_state:
        flash(f'Invalid state parameter. Received: {state}, Stored: {stored_state}', 'danger')
        return redirect(url_for('login'))
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('Authorization failed. No code provided.', 'danger')
        return redirect(url_for('login'))
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    try:
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        # Verify and decode ID token
        idinfo = id_token.verify_oauth2_token(
            tokens['id_token'],
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        # Extract user info
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name', email.split('@')[0])
        picture = idinfo.get('picture', '')
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        mode = session.pop('oauth_mode', 'login')
        
        if not user:
            if mode == 'login':
                flash('No account found with this Google email. Please register first.', 'warning')
                return redirect(url_for('register'))

            # Automatic Registration for Google Users (only if in register mode)
            print(f"DEBUG: New Google User detected via Register mode: {email}. Creating account...")
            
            # Generate a random password for Google-only users (they can change it later or use forgot password)
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            hashed_pw = bcrypt.generate_password_hash(random_password).decode('utf-8')
            
            try:
                # Default role logic
                role = 'Client'
                is_admin = False
                perms = '[]'
                if email == 'royalvistatechsolutions@gmail.com':
                    role = 'Super Admin'
                    is_admin = True
                    perms = json.dumps(['jobs', 'newsletters', 'chatbot', 'users'])
                
                user = User(
                    username=name, 
                    email=email, 
                    password=hashed_pw, 
                    google_id=google_id,
                    role=role, 
                    is_admin=is_admin, 
                    permissions=perms, 
                    custom_user_id=gen_user_id()
                )
                db.session.add(user)
                db.session.commit()
                
                # Prepare sync data for background thread
                sync_data = {
                    'id': user.id, 'username': user.username, 'email': user.email,
                    'phone_number': user.phone_number, 'password': user.password,
                    'google_id': user.google_id, 'custom_user_id': user.custom_user_id,
                    'is_admin': user.is_admin, 'is_active_status': user.is_active_status,
                    'is_subscribed': user.is_subscribed, 'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'permissions': user.permissions, 'role': user.role, 'profile_edited_count': user.profile_edited_count
                }
                threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'User')).start()

                # Audit & Notification (Threaded to prevent blocking redirections/502s)
                def background_notify():
                    log_audit(db, user.id, "User Registered via Google")
                    add_notification(user.id, "Welcome to RoyalVista!", 
                                     "Your account has been created via Google.", 
                                     link=url_for('dashboard'), 
                                     template='emails/welcome.html')
                
                threading.Thread(target=background_notify).start()
                
                flash(f'Welcome to RoyalVista, {name}! Your account has been created.', 'success')
                session['new_google_user'] = True
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG: Google Registration Error: {e}")
                flash('An error occurred while creating your account. Please try again.', 'danger')
                return redirect(url_for('register'))
        else:
            # Update Google ID if not set
            if not user.google_id:
                user.google_id = google_id
                db.session.commit()
            flash(f'Welcome back, {user.username}!', 'success')
        
        # Log in the user
        login_user(user)
        log_audit(db, user.id, "User Login via Google")
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        print(f"Google OAuth Error: {e}")
        flash('Authentication failed. Please try again.', 'danger')
        return redirect(url_for('login'))

@app.route("/profile/update", methods=['POST'])
@login_required
def update_profile():
    new_username = request.form.get('username')
    new_phone = request.form.get('phone')
    description = request.form.get('description', '')

    if not validate_inputs(new_username, new_phone):
        flash('Username and Phone are required.', 'danger')
        return redirect(url_for('dashboard'))

    if not validate_phone_format(new_phone):
        flash('Invalid phone number format. Only digits and optional + allowed.', 'danger')
        return redirect(url_for('dashboard'))

    # Business Logic: Modify once directly, then request admin
    if current_user.profile_edited_count == 0:
        current_user.username = new_username
        current_user.phone_number = new_phone
        current_user.profile_edited_count += 1
        db.session.commit()
        
        # Sync update to Sheets
        sync_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'phone_number': current_user.phone_number,
            'password': current_user.password,
            'google_id': current_user.google_id,
            'custom_user_id': current_user.custom_user_id,
            'is_admin': current_user.is_admin,
            'is_active_status': current_user.is_active_status,
            'is_subscribed': current_user.is_subscribed,
            'created_at': current_user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'permissions': current_user.permissions,
            'role': current_user.role,
            'profile_edited_count': current_user.profile_edited_count
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'User')).start()
        
        log_audit(db, current_user.id, "Profile Updated Directly")
        flash('Profile updated successfully!', 'success')
    else:
        # Create a modification request for Admin
        if not description:
            flash('Please provide a reason for this change as you have already modified your profile once.', 'warning')
            return redirect(url_for('dashboard'))
            
        req = ProfileRequest(
            user_id=current_user.id,
            new_username=new_username,
            new_phone=new_phone,
            description=description
        )
        db.session.add(req)
        db.session.commit()
        
        # Sync to Sheets
        sync_data = {
            'id': req.id,
            'user_id': req.user_id,
            'new_name': req.new_username,
            'new_phone': req.new_phone,
            'description': req.description,
            'status': req.status
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'ProfileRequest')).start()
        
        # Notify Admin
        admin = User.query.filter_by(is_admin=True).first()
        if admin:
            add_notification(
                admin.id,
                "Profile Change Request",
                f"User {current_user.username} has requested a profile change.",
                link=url_for('dashboard', _anchor='tab-profile-requests')
            )
            
        flash('Your profile change request has been sent to the admin for approval.', 'info')

    return redirect(url_for('dashboard'))

@app.route("/admin/profile-request/<int:rid>/<action>")
@login_required
def handle_profile_request(rid, action):
    if not current_user.is_admin:
        return redirect(url_for('home'))
        
    req = ProfileRequest.query.get_or_404(rid)
    if action == 'approve':
        user = User.query.get(req.user_id)
        if user:
            user.username = req.new_username
            user.phone_number = req.new_phone
            user.profile_edited_count += 1
            req.status = 'Approved'
            db.session.commit()
            
            add_notification(
                user.id,
                "Profile Change Approved",
                "Your profile has been updated by the admin.",
                link=url_for('dashboard')
            )
            flash(f"Approved change for {user.username}", 'success')
    elif action == 'reject':
        req.status = 'Rejected'
        db.session.commit()
        add_notification(
            req.user_id,
            "Profile Change Rejected",
            "Your profile change request was not approved by the admin.",
            link=url_for('dashboard')
        )
        flash("Request rejected.", 'info')
        
    return redirect(url_for('dashboard', _anchor='tab-profile-requests'))
        

@app.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            # In a real app, generate a token and send a link.
            # Here we simulate sending a reset link.
            reset_token = secrets.token_urlsafe(16)
            # Store token in DB or redis if implementing full flow. 
            # For now, we will just email them a notification that they can reset.
            send_email_styled(email, "Password Reset Request", 'emails/base_email.html',
                              # Re-using base template for simplicity or create a specific one
                              subject="Password Reset",
                              body=f"Hello {user.username},<br><br>We received a request to reset your password. <br>Since this is a demo, please contact admin to reset credentials or just use Google Login if available.")
            flash(f'Recovery instructions sent to {email}.', 'info')
        else:
            flash(f'Recovery instructions sent to {email}.', 'info') # Same msg for security
            
        return redirect(url_for('login'))
    return render_template('login.html', mode='forgot')

@app.route("/contact", methods=['POST'])
def contact():
    name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    service = request.form.get('service')
    msg = request.form.get('message')
    
    if not validate_inputs(name, email, msg):
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('home', _anchor='contact'))

    data = {
        'full_name': name,
        'email': email,
        'phone': phone,
        'service': service,
        'message': msg
    }
    # Parallel Storage: Database & Sheets
    try:
        new_lead = Lead(full_name=name, email=email, phone=phone, service=service, message=msg)
        db.session.add(new_lead)
        db.session.commit()
        
        # Background Sync to Sheets
        threading.Thread(target=sync_to_google_sheets, args=(data, 'Lead')).start()
    except Exception as e:
        print(f"Lead Storage Error: {e}")
        # Even if DB fails, sheets might work, or vice versa. 
        # But we want them parallel.
    
    # Email User
    send_email_styled(email, f"We've Received Your Inquiry - {name}", 'emails/lead_confirmation.html', 
                      user_name=name, service_name=service, message=msg)
    
    # Notify Admin
    admin = User.query.filter_by(role='Super Admin').first()
    if admin:
        send_email_styled(admin.email, "New Lead Received", 'emails/admin_alert.html', 
                          event_type='Contact Form Inquiry', 
                          event_details=f"Service: {service} | Message: {msg}", 
                          user_name=name, user_email=email)
    
    flash('Thank you! Your message has been sent successfully.', 'success')
    return redirect(url_for('home', _anchor='contact'))

    flash('Inquiry received! Our team will contact you shortly.', 'success')
    return redirect(url_for('home'))

@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        # Explicitly include the ID and Username in the action string so the history is clear
        action_msg = f"User Logout - {current_user.username} [{current_user.custom_user_id}]"
        log_audit(db, current_user.id, action_msg)
    logout_user()
    return redirect(url_for('home'))

@app.route("/dashboard", methods=['GET', 'POST'])
@login_required
def dashboard():
    must_update_profile = session.pop('new_google_user', False)
    if current_user.is_admin:
        if request.method == 'POST':
            # Portfolio Management
            if 'add_portfolio' in request.form:
                title = request.form.get('title')
                client = request.form.get('client_name')
                cat = request.form.get('category')
                file = request.files.get('image')
                image_url = 'assets/images/portfolio-web.png'
                if file:
                    fname = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                    file.save(file_path)
                    
                    # Apply Watermark
                    apply_watermark(file_path)
                    
                    image_url = f'assets/uploads/{fname}'
                
                item = PortfolioItem(title=title, client_name=client, category=cat, image_url=image_url)
                db.session.add(item)
                db.session.commit()
                log_audit(db, current_user.id, "Portfolio Item Added", f"Item: {title}")
                flash('Portfolio item updated category-wise.', 'success')

            # Status Update with Output Prompt
            if 'update_status' in request.form:
                oid = request.form.get('order_id')
                status = request.form.get('status')
                note = request.form.get('note', '')
                file = request.files.get('timeline_file')
                order = Order.query.get(oid)
                if order:
                    order.status = status
                    file_url = None
                    file_type = None
                    
                    if file and file.filename:
                        fname = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                        file_url = f'assets/uploads/{fname}'
                        ext = fname.lower().split('.')[-1]
                        if ext in ['jpg', 'png', 'jpeg', 'gif']:
                            file_type = 'image'
                            # Apply Watermark immediately if it is an image
                            try:
                                full_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], fname)
                                apply_watermark(full_path)
                            except Exception as e:
                                print(f"Failed to apply watermark to order image: {e}")
                        elif ext in ['mp4']: file_type = 'video'
                        elif ext in ['pdf']: file_type = 'document'

                    # Auto-add to Portfolio if a file is present or explicitly completed, regardless of status being technically 'Completed' (handles Reopened/In Progress updates with potential deliverables)
                    # Auto-add to Portfolio Logic
                    # Trigger if status is Completed/In-Progress AND (Input provided OR it's a final delivery)
                    if status in ['Completed', 'Reopened', 'In Progress']:
                        output_url = request.form.get('output_url')
                        should_add = False
                        
                        # 1. If explicit output provided now
                        if output_url or file_url:
                            should_add = True
                        # 2. If marking Completed, try to find ANY deliverable to showcase
                        elif status == 'Completed':
                            should_add = True
                            
                        if should_add:
                            # Determine Category
                            service_name = order.service_name.strip()
                            cat_map = {
                                'Web Design': 'web', 'Logo Design': 'logo', 'Video Editing': 'video',
                                'Thumbnails': 'thumbnails', 'Posters & Ads': 'ads',
                                'SEO Services': 'seo', 'Social Media Marketing': 'seo',
                                'Wedding Invitations': 'invitations'
                            }
                            p_cat = cat_map.get(service_name, service_name.split(' ')[0].lower())
                            
                            # Determine Image
                            p_image = None
                            if file_url and file_type == 'image':
                                p_image = file_url
                            else:
                                # Look for latest image in timeline and ensure it is valid
                                last_img = OrderTimeline.query.filter_by(order_id=order.id, file_type='image').order_by(OrderTimeline.timestamp.desc()).first()
                                if last_img:
                                    p_image = last_img.file_url
                                else:
                                    p_image = f"assets/images/portfolio-{p_cat}.png"
                            
                            p_title = f"{service_name} Project"
                            
                            # Avoid Duplicates (Basic check by title and client)
                            if not PortfolioItem.query.filter_by(title=p_title, client_name=order.client.username).first():
                                p_item = PortfolioItem(
                                    title=p_title,
                                    client_name=order.client.username,
                                    category=p_cat,
                                    image_url=p_image,
                                    external_link=output_url if output_url else (file_url if file_url else '#')
                                )
                                db.session.add(p_item)
                                flash('Project automatically added to Portfolio!', 'success')
                    
                    note_text = f"Status updated to {status}."
                    if note: note_text += f" Note: {note}"
                    
                    db.session.add(OrderTimeline(order_id=order.id, action_type='Status Updated', 
                                              performed_by='Admin', note=note_text,
                                              file_url=file_url, file_type=file_type))
                    db.session.commit()
                    
                    # Notify User with styled email
                    add_notification(order.user_id, "Order Updated", f"Order {order.custom_order_id} is now {status}.", 
                                     link=url_for('dashboard', _anchor=f'order-{order.id}'),
                                     template='emails/status_update.html',
                                     order_id=order.custom_order_id,
                                     status=status,
                                     note=note)
                    
                    flash(f'Order {order.custom_order_id} updated.', 'success')

            if 'reply_ticket' in request.form:
                tid = request.form.get('ticket_id')
                reply = request.form.get('reply')
                ticket = SupportTicket.query.get(tid)
                if ticket:
                    ticket.status = 'Resolved'
                    add_notification(ticket.user_id, "Support Ticket Resolved", f"Re: {ticket.subject} - {reply}", 
                                     link=url_for('dashboard', _anchor=f'ticket-{ticket.id}'))
                    db.session.commit()
                    flash(f'Ticket #{tid} resolved.', 'info')

            if 'update_content' in request.form:
                key = request.form.get('key')
                val = request.form.get('value')
                item = SiteContent.query.get(key)
                if not item:
                    item = SiteContent(key=key, value=val)
                    db.session.add(item)
                else:
                    item.value = val
                db.session.commit()
                flash(f'CMS Item {key} updated.', 'success')

            return redirect(url_for('dashboard'))

        # Analytics
        stats = {
            'total_users': User.query.count(),
            'total_orders': Order.query.count(),
            'submitted': Order.query.filter_by(status='Submitted').count(),
            'in_progress': Order.query.filter_by(status='In Progress').count(),
            'completed': Order.query.filter_by(status='Completed').count()
        }
        
        # Search & Filtering
        q = request.args.get('q', '')
        f_status = request.args.get('status', '')
        orders_query = Order.query
        if q:
            orders_query = orders_query.join(User).filter(
                (Order.custom_order_id.contains(q)) | 
                (User.username.contains(q)) | 
                (User.email.contains(q)) | 
                (User.phone_number.contains(q)) |
                (User.custom_user_id.contains(q))
            )
        if f_status:
            orders_query = orders_query.filter(Order.status == f_status)
        
        # User Search
        uq = request.args.get('uq', '')
        users_query = User.query
        if uq:
            users_query = users_query.filter(
                (User.username.contains(uq)) | 
                (User.email.contains(uq)) | 
                (User.phone_number.contains(uq)) |
                (User.custom_user_id.contains(uq))
            )

        orders = orders_query.order_by(Order.created_at.desc()).all()
        users = users_query.all()
        portfolio = PortfolioItem.query.all()
        audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all()
        tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
        
        # Count unread/open tickets
        unread_tickets_count = SupportTicket.query.filter(SupportTicket.status != 'Resolved', SupportTicket.status != 'Closed').count()
        
        content = {item.key: item.value for item in SiteContent.query.all()}
        scheduled_emails = ScheduledEmail.query.order_by(ScheduledEmail.created_at.desc()).all()
        all_jobs = Job.query.order_by(Job.created_at.desc()).all()
        profile_requests = ProfileRequest.query.order_by(ProfileRequest.created_at.desc()).all()
        leads = Lead.query.order_by(Lead.created_at.desc()).all()
        
        return render_template('dashboard.html', mode='admin', orders=orders, stats=stats, users=users, 
                               portfolio=portfolio, audit_logs=audit_logs, content=content, 
                               tickets=tickets, unread_tickets_count=unread_tickets_count,
                               scheduled_emails=scheduled_emails, all_jobs=all_jobs, all_users=User.query.all(),
                               profile_requests=profile_requests, must_update_profile=must_update_profile, leads=leads)
    
    else:
        # User View
        # Check if new user needs to update profile
        # Condition: Phone is placeholder OR user has never edited profile (for Google users)
        if (current_user.phone_number == 'Google Account' or 
            (current_user.google_id and current_user.profile_edited_count == 0)):
            must_update_profile = True
            flash('Please update your contact details to proceed.', 'warning')

        my_profile_requests = ProfileRequest.query.filter_by(user_id=current_user.id).order_by(ProfileRequest.created_at.desc()).all()
        
        if request.method == 'POST' and 'request_service' in request.form:
            sid = request.form.get('service_id')
            service = Service.query.get(sid)
            details = request.form.get('details')
            
            if not validate_inputs(sid, details):
                flash('Please select a service and provide project details.', 'danger')
                return redirect(url_for('dashboard'))
                
            if service:
                try:
                    cust_id = gen_order_id()
                    order = Order(custom_order_id=cust_id, user_id=current_user.id, service_id=service.id, 
                                service_name=service.title, details=details)
                    db.session.add(order)
                    db.session.commit()
                    db.session.add(OrderTimeline(order_id=order.id, action_type='Order Created', performed_by=current_user.username))
                    db.session.commit()
                    
                    # Background Sync to Sheets
                    sync_data = {
                        'order_id': cust_id, 
                        'user_id': current_user.custom_user_id, 
                        'phone': current_user.phone_number,
                        'user': current_user.email, 
                        'service': service.title, 
                        'details': details
                    }
                    threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Order')).start()
                except Exception as e:
                    db.session.rollback()
                    print(f"Order Storage Error: {e}")
                    flash('An error occurred while creating your order.', 'danger')
                    return redirect(url_for('dashboard'))
                
                # Notify User
                add_notification(current_user.id, "Order Confirmed", f"Your project {cust_id} has been successfully submitted.", 
                                 link=url_for('dashboard', _anchor=f'order-{order.id}'),
                                 template='emails/new_order.html',
                                 order_id=cust_id,
                                 service_name=service.title)
                
                # Admin notification
                admin = User.query.filter_by(is_admin=True).first()
                if admin:
                    add_notification(admin.id, "New Order", f"Order {cust_id} from {current_user.username}", 
                                     link=url_for('dashboard', _anchor=f'order-{order.id}'),
                                     template='emails/admin_alert.html',
                                     event_type='New Order',
                                     event_details=f"Order {cust_id} for {service.title}",
                                     user_name=current_user.username,
                                     user_email=current_user.email)
                
                flash(f'Order {cust_id} placed!', 'success')
            return redirect(url_for('dashboard'))

        if request.method == 'POST' and 'create_ticket' in request.form:
            subject = request.form.get('subject')
            desc = request.form.get('description')
            priority = request.form.get('priority', 'Normal')
            order_id = request.form.get('order_id')
            
            if not validate_inputs(subject, desc, order_id):
                flash('Please fill in all ticket fields.', 'danger')
                return redirect(url_for('dashboard'))
                
            if not order_id:
                flash('Please select an order for this ticket.', 'error')
                return redirect(url_for('dashboard'))
                
            try:
                ticket = SupportTicket(user_id=current_user.id, order_id=order_id, subject=subject, description=desc, priority=priority,
                                    custom_ticket_id=gen_ticket_id())
                db.session.add(ticket)
                db.session.commit()
                
                # Parallel Sync to Sheets
                sync_to_google_sheets({'ticket_id': ticket.custom_ticket_id, 'user': current_user.email, 'order_id': order_id, 
                                    'subject': subject, 'priority': priority}, category='Ticket')
            except Exception as e:
                db.session.rollback()
                print(f"Ticket Storage Error: {e}")
                flash('An error occurred while creating your ticket.', 'danger')
                return redirect(url_for('dashboard'))

            # Notify Admin
            admin = User.query.filter_by(is_admin=True).first()
            if admin:
                add_notification(admin.id, "New Support Ticket", f"Ticket from {current_user.username}: {subject}", 
                                 link=url_for('dashboard', _anchor=f'ticket-{ticket.id}'),
                                 template='emails/admin_alert.html',
                                 event_type='Support Ticket',
                                 event_details=f"Subject: {subject} | Priority: {priority}",
                                 user_name=current_user.username,
                                 user_email=current_user.email)
            flash('Ticket created.', 'success')
            return redirect(url_for('dashboard'))

        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        services = Service.query.filter_by(active=True).all()
        tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all()
        return render_template('dashboard.html', mode='user', orders=orders, services=services, tickets=tickets, 
                               profile_requests=my_profile_requests, must_update_profile=must_update_profile)

@app.route("/notifications/read/<int:nid>")
@login_required
def mark_read(nid):
    notification = Notification.query.get_or_404(nid)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return jsonify({'status': 'success'})

@app.route("/download_invoice/<int:order_id>")
@login_required
def download_invoice(order_id):
    order = Order.query.get_or_404(order_id)
    if not current_user.is_admin and order.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
    filename = f"RoyalVista_Tech_Solutions_Order_{order.custom_order_id}.pdf"
    return send_file(generate_invoice_pdf(order), as_attachment=True, download_name=filename)

@app.route("/api/chatbot", methods=['POST'])
def chatbot():
    msg = request.json.get('message', '')
    if not msg:
        return jsonify({'error': 'No message provided'}), 400
    
    # Greetings
    if any(g in msg.lower() for g in ['hi', 'hello', 'hey', 'start']):
        return jsonify({'reply': "Hello! I'm the RoyalVista AI assistant. Ask me about our services, pricing, or company policies."})

    # Use AI Engine (RAG)
    response = rv_ai.get_chatbot_response(msg)
    
    if response:
        # Append citation if available
        reply = response['reply']
        if response['citations']:
            reply += f"<br><small class='text-muted' style='font-size:0.75rem; display:block; margin-top:5px;'>({response['citations'][0]})</small>"
        return jsonify({'reply': reply})
    
    # Fallback / Escalation
    return jsonify({
        'reply': "I'm sorry, I don't have enough specific information on that. Would you like to connect with a human expert?",
        'cta': {
            'text': 'Talk to Support',
            'link': url_for('home', _anchor='contact')
        }
    })


@app.route("/admin/portfolio/manage", methods=['POST'])
@login_required
def manage_portfolio():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    action = request.form.get('action')
    title = request.form.get('title')
    client_name = request.form.get('client_name')
    category = request.form.get('category')
    link = request.form.get('external_link')
    
    file = request.files.get('image')
    image_url = None
    if file and file.filename:
        fname = secure_filename(f"p_{int(datetime.utcnow().timestamp())}_{file.filename}")
        file_path = os.path.join(app.root_path, 'static/assets/portfolio', fname)
        file.save(file_path)
        
        # Apply Watermark
        apply_watermark(file_path)
        
        image_url = f'assets/portfolio/{fname}'

    if action == 'add':
        item = PortfolioItem(title=title, client_name=client_name, category=category, external_link=link, image_url=image_url)
        db.session.add(item)
        flash('Portfolio item added.', 'success')
        
    elif action == 'edit':
        pid = request.form.get('id')
        item = PortfolioItem.query.get(pid)
        if item:
            item.title = title
            item.client_name = client_name
            item.category = category
            item.external_link = link
            if image_url: item.image_url = image_url
            flash('Portfolio item updated.', 'success')

    db.session.commit()
    
    # Sync to Sheets
    if action in ['add', 'edit'] and item:
        sync_data = {
            'id': item.id,
            'title': item.title,
            'client_name': item.client_name,
            'category': item.category,
            'image_url': item.image_url,
            'active': item.active
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Portfolio')).start()

    return redirect(url_for('dashboard'))

@app.route("/delete_portfolio/<int:item_id>")
@login_required
def delete_portfolio(item_id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    item = PortfolioItem.query.get_or_404(item_id)
    
    # Optional: Delete file from server
    if item.image_url and 'default' not in item.image_url:
        try:
            file_path = os.path.join(app.root_path, 'static', item.image_url)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file for portfolio item {item_id}: {e}")
            
    db.session.delete(item)
    db.session.commit()
    flash('Portfolio item deleted.', 'info')
    return redirect(url_for('dashboard'))

@app.route("/admin/edit_user", methods=['POST'])
@login_required
def edit_user():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    uid = request.form.get('user_id')
    user = User.query.get(uid)
    if user:
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.phone_number = request.form.get('phone')
        user.is_active_status = True if request.form.get('status') == 'active' else False
        db.session.commit()
        flash(f'User {user.username} updated.', 'success')
    return redirect(url_for('dashboard'))

@app.route("/admin/backup")
@login_required
def trigger_backup():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    if backup_db():
        flash('Database backup successful.', 'success')
    else:
        flash('Backup failed.', 'danger')
    return redirect(url_for('dashboard'))

@app.route("/admin/newsletter/preview", methods=['POST'])
@login_required
def newsletter_preview():
    if not current_user.is_admin: return jsonify({'error': 'Unauthorized'}), 403
    subject = request.json.get('subject')
    body = request.json.get('body')
    # Render preview using the actual template
    preview_html = render_template('emails/newsletter.html', subject=subject, body=body)
    return jsonify({'html': preview_html})

@app.route("/admin/newsletter/action", methods=['POST'])
@login_required
def newsletter_action():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    subject = request.form.get('subject')
    body = request.form.get('body')
    action = request.form.get('action') # 'send_now' or 'schedule'
    recipient_emails = request.form.getlist('recipients')
    
    if not validate_inputs(subject, body):
        flash('Subject and Body are required for the newsletter.', 'danger')
        return redirect(url_for('dashboard'))

    if not recipient_emails:
        flash('Please select at least one recipient.', 'danger')
        return redirect(url_for('dashboard'))

    if action == 'send_now':
        success = 0
        for email in recipient_emails:
            if send_email_styled(email, subject, 'emails/newsletter.html', subject=subject, body=body):
                success += 1
        
        # Log as sent email
        new_mail = ScheduledEmail(subject=subject, body=body, recipients=json.dumps(recipient_emails), 
                                 status='Sent', sent_at=datetime.utcnow())
        db.session.add(new_mail)
        db.session.commit()
        
        # Sync to Sheets
        sync_data = {
            'id': new_mail.id,
            'subject': new_mail.subject,
            'status': new_mail.status,
            'scheduled': False,
            'sent_at': new_mail.sent_at.strftime('%Y-%m-%d %H:%M:%S') if new_mail.sent_at else None
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Email')).start()
        
        flash('Broadcast sent successfully!', 'success')
        
    elif action == 'schedule':
        schedule_time_str = request.form.get('schedule_time')
        if not schedule_time_str:
            flash('Please select a date and time for scheduling.', 'danger')
            return redirect(url_for('dashboard'))
        
        # Handle IST conversion
        ist = pytz.timezone('Asia/Kolkata')
        local_time = datetime.strptime(schedule_time_str, '%Y-%m-%dT%H:%M')
        # We assume the input is in IST as requested
        sched_time_ist = ist.localize(local_time).astimezone(pytz.utc).replace(tzinfo=None)
        
        new_mail = ScheduledEmail(subject=subject, body=body, recipients=json.dumps(recipient_emails), 
                                 scheduled_time=sched_time_ist, status='Scheduled')
        db.session.add(new_mail)
        db.session.commit()
        
        # Sync to Sheets
        sync_data = {
            'id': new_mail.id,
            'subject': new_mail.subject,
            'status': new_mail.status,
            'scheduled': True,
            'sent_at': None
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Email')).start()
        
        flash('Broadcast scheduled successfully!', 'success')

    return redirect(url_for('dashboard'))

@app.route("/admin/newsletter/delete/<int:mid>")
@login_required
def delete_scheduled_email(mid):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    email = ScheduledEmail.query.get_or_404(mid)
    if email.status == 'Scheduled':
        db.session.delete(email)
        db.session.commit()
        flash('Scheduled email cancelled.', 'info')
    else:
        db.session.delete(email)
        db.session.commit()
        flash('Email record deleted.', 'info')
    return redirect(url_for('dashboard'))

# --- Job Posting Routes ---

@app.route("/jobs")
def jobs():
    q = request.args.get('q', '')
    cat_filter = request.args.get('category', '')
    sort_filter = request.args.get('sort', 'recent')
    
    query = Job.query.filter_by(status='Posted')
    if q:
        query = query.filter((Job.title.contains(q)) | (Job.description.contains(q)))
    if cat_filter:
        query = query.filter(Job.categories.contains(cat_filter))
        
    if sort_filter == 'alpha':
        query = query.order_by(Job.title.asc())
    else:
        query = query.order_by(Job.posted_at.desc())
        
    jobs = query.all()
    categories = JobCategory.query.all()
    
    sub_ids = []
    if current_user.is_authenticated:
        sub_ids = [s.category_id for s in current_user.job_subscriptions]
        
    return render_template('jobs.html', jobs=jobs, categories=categories, sub_ids=sub_ids)

@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    if job.status != 'Posted' and (not current_user.is_authenticated or not current_user.is_admin):
        flash('This job posting is not available.', 'info')
        return redirect(url_for('jobs'))
    return render_template('job_detail.html', job=job)

@app.route("/jobs/subscribe", methods=['POST', 'GET'])
def job_subscribe():
    if request.method == 'POST':
        email = request.form.get('email')
        cat_ids = request.form.getlist('categories')
        
        user = None
        if current_user.is_authenticated:
            user = current_user
        else:
            if not email:
                flash('Email is required for subscription.', 'danger')
                return redirect(url_for('jobs'))
            user = User.query.filter_by(email=email).first()
            if not user:
                # Create a minimal user or handle as guest? 
                # For consistency, let's ask them to login/register first if we want full features, 
                # but for simplicity let's require at least an email check.
                flash('Please log in or register to manage your job subscriptions.', 'info')
                return redirect(url_for('login'))
        
        # Update subscriptions
        from models import JobSubscription
        # Clear existing for these categories or just add new? 
        # User requested: "Users can select one or more job categories"
        
        # Clear current for this user
        JobSubscription.query.filter_by(user_id=user.id).delete()
        
        for cid in cat_ids:
            sub = JobSubscription(user_id=user.id, category_id=int(cid))
            db.session.add(sub)
            db.session.commit() # Commit each to get ID or just commit after loop
            
            # Sync to Sheets
            sync_data = {
                'id': sub.id,
                'user_id': user.custom_user_id if user else "Guest",
                'category_id': sub.category_id
            }
            threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Subscription')).start()
            
        db.session.commit()
        flash('Subscription preferences updated!', 'success')
        return redirect(url_for('jobs'))
    
    # GET shows subscription management (could be a modal or separate page)
    return redirect(url_for('jobs'))

@app.route("/api/jobs/share/<int:job_id>", methods=['POST'])
@csrf.exempt # Exempting for API simplicity, or use JS to pass token
def share_job(job_id):
    job = Job.query.get_or_404(job_id)
    job.share_count += 1
    db.session.commit()
    return jsonify({'status': 'success', 'count': job.share_count})

@app.route("/admin/jobs/action", methods=['POST'])
@login_required
@permission_required('jobs')
def admin_job_action():
    action_type = request.form.get('action_type') # create, edit, delete
    post_status = request.form.get('post_status') # Post Now, Schedule, Save as Draft
    
    title = request.form.get('title')
    desc = request.form.get('description')
    cats = ";".join(request.form.getlist('categories'))
    years = request.form.get('eligible_years')
    link = request.form.get('external_link')
    
    if action_type in ['create', 'edit']:
        if not validate_inputs(title, desc, link):
            flash('Title, Description and Application Link are required.', 'danger')
            return redirect(url_for('dashboard', _anchor='tab-jobs'))

    image_url = None
    file = request.files.get('image')
    if file and file.filename:
        fname = secure_filename(f"job_{int(datetime.utcnow().timestamp())}_{file.filename}")
        file.save(os.path.join(app.root_path, 'static/assets/jobs', fname))
        image_url = f'assets/jobs/{fname}'

    if action_type == 'create':
        job = Job(title=title, description=desc, categories=cats, eligible_years=years, external_link=link, image_url=image_url)
        db.session.add(job)
    elif action_type == 'delete':
        jid = request.form.get('job_id')
        job = Job.query.get(jid)
        if job:
            db.session.delete(job)
            db.session.commit()
            flash('Job deleted successfully.', 'info')
            return redirect(url_for('dashboard', _anchor='tab-jobs'))
    else:
        jid = request.form.get('job_id')
        job = Job.query.get(jid)
        if job:
            job.title = title
            job.description = desc
            job.categories = cats
            job.eligible_years = years
            job.external_link = link
            if image_url: job.image_url = image_url

    if job:
        if post_status == 'Post Now':
            job.status = 'Posted'
            job.posted_at = datetime.utcnow()
            db.session.commit()
            notify_job_subscribers(job)
            flash('Job posted successfully!', 'success')
        elif post_status == 'Schedule':
            time_str = request.form.get('schedule_time')
            if time_str:
                job.status = 'Scheduled'
                # Assuming UI provides local time, we treat it as UTC for simplicity or convert
                # To be robust, we'd use a TZ but utcnow is standard for internal comparison
                job.scheduled_time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M')
                flash('Job scheduled successfully!', 'success')
            else:
                flash('Schedule time is required.', 'danger')
        else:
            job.status = 'Draft'
            flash('Job saved as draft.', 'info')

    db.session.commit()
    
    # Sync to Sheets
    if action_type in ['create', 'edit'] and job:
        sync_data = {
            'id': job.id,
            'title': job.title,
            'categories': job.categories,
            'eligible_years': job.eligible_years,
            'status': job.status,
            'share_count': job.share_count
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Job')).start()

    return redirect(url_for('dashboard', _anchor='tab-jobs'))



@app.route("/admin/roles/update", methods=['POST'])
@login_required
def admin_roles_update():
    if current_user.role != 'Super Admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    target_email = request.form.get('email')
    target_role = request.form.get('role')
    perms = request.form.getlist('permissions')
    
    user = User.query.filter_by(email=target_email).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    if target_email == current_user.email:
        flash('Security Alert: You cannot modify your own permissions or role to prevent accidental lockout.', 'warning')
        return redirect(url_for('dashboard', _anchor='tab-permissions'))
    
    if target_role in ['Admin', 'Limited Admin']:
        user.is_admin = True
    elif target_role == 'Client':
        user.is_admin = False
    
    user.role = target_role
    user.permissions = json.dumps(perms)
    db.session.commit()
    
    log_audit(db, current_user.id, f"Updated permissions for {target_email} to {target_role}")
    flash(f"Permissions updated for {target_email}", 'success')
    return redirect(url_for('dashboard', _anchor='tab-permissions'))

# Initialize database and default content
init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)

