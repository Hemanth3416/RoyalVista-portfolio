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
from datetime import datetime, timezone, timedelta
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

# Google Drive Config - REMOVED (Using ImgBB)
from utils import upload_to_imgbb

# Check for environment variable, fallback to dev key if not set
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_royalvista_key_2026')
csrf = CSRFProtect(app)

@app.route("/healthz")
def healthz():
    return "OK", 200

# DATABASE CONNECTION
db_uri = os.environ.get('DATABASE_URL')
if db_uri:
    # Aggressively extract URL starting with postgresql:// or postgres://
    # This handles "psql 'url'", quotes, and other noise.
    match = re.search(r'(postgresql?://[^\s\'"]+)', db_uri)
    if match:
        db_uri = match.group(1)
        # SQLAlchemy requires 'postgresql://' instead of 'postgres://'
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
        # Safe Log: Mask password (handle various formats)
        safe_uri = re.sub(r'(://[^:]+):([^@]+)(@)', r'\1****\3', db_uri)
        print(f"📡 DATABASE_URL DETECTED: {safe_uri}", flush=True)
    else:
        print("⚠️ DATABASE_URL format unrecognized. Using SQLite.", flush=True)
        db_uri = "sqlite:///site.db"

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'assets', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

try:
    # Check if URI is valid
    from sqlalchemy.engine.url import make_url
    make_url(app.config['SQLALCHEMY_DATABASE_URI'])
    db.init_app(app)
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
        print("✅ Connected to: PostgreSQL Pool", flush=True)
except Exception as e:
    print(f"❌ DATABASE ERROR: Fallback to SQLite. Reason: {e}", flush=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
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
        from models import ScheduledEmail
        emails = ScheduledEmail.query.filter(
            ScheduledEmail.status == 'Scheduled',
            ScheduledEmail.scheduled_time <= datetime.now(timezone.utc)
        ).all()
        for email in emails:
            try:
                recipients = json.loads(email.recipients)
                for addr in recipients:
                    send_email_styled(addr, email.subject, 'emails/newsletter.html', 
                                         subject=email.subject, body=email.body)
                
                email.status = 'Sent'
                email.sent_at = datetime.now(timezone.utc)
                db.session.commit()
            except Exception as e:
                email.status = 'Failed'
                email.error_log = str(e)
                db.session.commit()
        
        # Process Jobs (Draft -> Posted)
        from models import Job
        scheduled_jobs = Job.query.filter(
            Job.status == 'Scheduled',
            Job.scheduled_time <= datetime.now(timezone.get_default_timezone() if hasattr(timezone, 'get_default_timezone') else timezone.utc)
        ).all()
        for job in scheduled_jobs:
            job.status = 'Posted'
            job.posted_at = datetime.now(timezone.utc)
            db.session.commit()

# Setup Scheduler (only one instance)
scheduler = BackgroundScheduler(timezone=pytz.UTC)
scheduler.add_job(func=process_scheduled_tasks, trigger="interval", minutes=1)

def send_email_styled(to_email, subject, template, **kwargs):
    """Sends a professional HTML email using a template."""
    from flask import render_template
    try:
        html_body = render_template(template, **kwargs)
        from utils import send_notification_email
        return send_notification_email(to_email, subject, html_body)
    except Exception as e:
        print(f"Email Template Error: {e}")
        return False

def add_notification(user_id, title, message, link=None, template=None, email_subject=None, **template_kwargs):
    """Utility to add a shared notification + optional email."""
    notif = Notification(user_id=user_id, title=title, message=message, link=link)
    db.session.add(notif)
    db.session.commit()
    
    # Standardized sync logic
    user = User.query.get(user_id)
    sync_data = {
        'id': notif.id,
        'user_id': user_id,
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

_maintenance_started = False

def init_db():
    global _maintenance_started
    if _maintenance_started:
        return
    _maintenance_started = True

    with app.app_context():
        # Step 1: Immediate Folders (Essential)
        for folder in ['instance', 'static/assets/uploads', 'static/assets/portfolio', 'static/assets/jobs']:
            os.makedirs(os.path.join(app.root_path, folder), exist_ok=True)
        
        # Step 2: Immediate Schema (Essential)
        db.create_all()

        # Step 3: Offload everything else to a background thread
        def run_maintenance(app_obj):
            with app_obj.app_context():
                try:
                    # Import models inside to avoid closure/UnboundLocal issues in some environments
                    from models import User, Service, JobCategory, PortfolioItem, Job, Order, SupportTicket
                    from utils import fetch_from_google_sheets
                    
                    # Generic check for columns (works for SQLite & Postgres)
                    from sqlalchemy import inspect
                    inspector = inspect(db.engine)
                    columns = [c['name'] for c in inspector.get_columns('user')]
                    
                    for col, dtype in [
                        ("is_subscribed", "BOOLEAN DEFAULT 1"), ("created_at", "DATETIME"), 
                        ("permissions", "TEXT"), ("role", "VARCHAR(20) DEFAULT 'Client'"), 
                        ("is_active_status", "BOOLEAN DEFAULT 1"), ("profile_edited_count", "INTEGER DEFAULT 0"), 
                        ("custom_user_id", "VARCHAR(20)")
                    ]:
                        if col not in columns:
                            try:
                                db.session.execute(db.text(f"ALTER TABLE \"user\" ADD COLUMN {col} {dtype}"))
                                db.session.commit()
                            except: db.session.rollback()

                    # Data Integrity & Seeding
                    if not User.query.filter_by(is_admin=True).first():
                        hashed_pw = bcrypt.generate_password_hash('RoyalVista@2026').decode('utf-8')
                        from models import User
                        db.session.add(User(username='RoyalVista Admin', email='royalvistatechsolutions@gmail.com', password=hashed_pw, is_admin=True, role='Super Admin', permissions=json.dumps(['jobs', 'newsletters', 'chatbot', 'users']), phone_number="+1234567890"))
                    
                    if not Service.query.first():
                        db.session.add_all([
                            Service(title='Web Design', description='Professional.', icon_class='fas fa-desktop'),
                            Service(title='Logo Design', description='Expert.', icon_class='fas fa-pen-nib'),
                            Service(title='Video Editing', description='High-quality.', icon_class='fas fa-video'),
                            Service(title='Thumbnails', description='Effective.', icon_class='fas fa-image'),
                            Service(title='Posters & Ads', description='Impactful.', icon_class='fas fa-ad'),
                            Service(title='Wedding Invitations', description='Elegant.', icon_class='fas fa-heart'),
                            Service(title='SEO Services', description='Visibility.', icon_class='fas fa-search'),
                            Service(title='Social Media Marketing', description='Presence.', icon_class='fas fa-share-alt'),
                            Service(title='Others', description='Custom.', icon_class='fas fa-ellipsis-h')
                        ])
                    
                    if not JobCategory.query.first():
                        db.session.add_all([JobCategory(name=n) for n in ['2024','2025','2026','Fresher','Experienced','Hackathons']])
                    
                    db.session.commit()

                    # Auto-Restore from Cloud (Comprehensive)
                    # Logic: If major tables are empty, we likely lost the SQLite file (Render restart)
                    needs_restore = PortfolioItem.query.first() is None or Job.query.first() is None
                    
                    if needs_restore:
                        print("☁️ CLOUD RESTORE: Local database appears empty. Syncing from Google Sheets...", flush=True)
                        
                        # Restore Users
                        u_data = fetch_from_google_sheets('User')
                        for u in u_data:
                            email = u.get('email')
                            if email and not User.query.filter_by(email=email).first():
                                try:
                                    db.session.add(User(
                                        username=u.get('username'), 
                                        email=email, 
                                        password=u.get('password'), 
                                        phone_number=u.get('phone_number'),
                                        is_admin=True if str(u.get('is_admin')).lower() == 'true' else False,
                                        custom_user_id=u.get('custom_user_id'),
                                        role=u.get('role', 'Client'),
                                        permissions=u.get('permissions')
                                    ))
                                except: pass
                        
                        # Restore Orders
                        o_data = fetch_from_google_sheets('Order')
                        for o in o_data:
                            oid = o.get('custom_order_id')
                            if oid:
                                try:
                                    db.session.add(Order(
                                        custom_order_id=oid,
                                        user_id=o.get('user_id'),
                                        service_name=o.get('service_name'),
                                        details=o.get('details'),
                                        status=o.get('status', 'Submitted'),
                                        output_url=o.get('output_url'),
                                        output_type=o.get('output_type')
                                    ))
                                except: pass

                        # Restore Tickets
                        t_data = fetch_from_google_sheets('Ticket')
                        for t in t_data:
                            tid = t.get('custom_ticket_id')
                            if tid:
                                try:
                                    db.session.add(Ticket(
                                        custom_ticket_id=tid,
                                        user_id=t.get('user_id'),
                                        order_id=t.get('order_id'),
                                        subject=t.get('subject'),
                                        description=t.get('description'),
                                        status=t.get('status', 'Open'),
                                        priority=t.get('priority', 'Medium')
                                    ))
                                except: pass

                        # Restore Portfolio
                        p_data = fetch_from_google_sheets('Portfolio')
                        for p in p_data:
                            if p.get('title'): 
                                db.session.add(PortfolioItem(
                                    title=p.get('title'), 
                                    client_name=p.get('client_name'), 
                                    category=p.get('category', 'Others'), 
                                    image_url=p.get('image_url'), 
                                    video_url=p.get('video_url'),
                                    external_link=p.get('external_link'),
                                    active=True if str(p.get('active')).lower() == 'true' else False
                                ))
                        
                        # Restore Jobs
                        j_data = fetch_from_google_sheets('Job')
                        for j in j_data:
                             if j.get('title'): 
                                 db.session.add(Job(
                                     title=j.get('title'), 
                                     description=j.get('description', 'Restored...'), 
                                     categories=j.get('categories'), 
                                     eligible_years=j.get('eligible_years'), 
                                     image_url=j.get('image_url'),
                                     external_link=j.get('external_link'),
                                     status=j.get('status', 'Posted'),
                                     share_count=int(j.get('share_count', 0)) if str(j.get('share_count')).isdigit() else 0
                                 ))
                        
                        db.session.commit()
                        print(f"✅ Cloud Restore SUCCESS: Local database is now populated.", flush=True)
                    
                    # Start Scheduler now that DB is ready
                    if not scheduler.running:
                        scheduler.start()
                        print("Background Scheduler Started.")
                except Exception as e:
                    print(f"Maintenance failed: {e}", flush=True)

        threading.Thread(target=run_maintenance, args=(app._get_current_object(),)).start()

init_db()

@app.context_processor
def inject_global_data():
    from models import JobCategory
    return {
        'now': datetime.now(pytz.UTC),
        'job_categories': JobCategory.query.all()
    }

@app.route("/")
def home():
    portfolio = PortfolioItem.query.filter_by(active=True).limit(6).all()
    services = Service.query.filter_by(active=True).all()
    # Also inject user notifications if logged in
    notifications = []
    if current_user.is_authenticated:
        notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    return render_template('index.html', portfolio=portfolio, services=services, notifications=notifications)

@app.route("/api/chat", methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    if not user_msg:
        return jsonify({'response': "How can I help you today?"})
    
    response = rv_ai.get_response(user_msg)
    return jsonify({'response': response})

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('username')
        email = request.form.get('email').lower()
        password = request.form.get('password')
        phone = request.form.get('phone_number')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        from app import gen_user_id
        user = User(username=name, email=email, password=hashed_pw, phone_number=phone, custom_user_id=gen_user_id())
        db.session.add(user)
        db.session.commit()
        
        # Prepare sync data for background thread
        sync_data = {
            'id': user.id, 'username': user.username, 'email': user.email,
            'phone_number': user.phone_number, 'password': user.password,
            'google_id': user.google_id, 'custom_user_id': user.custom_user_id,
            'is_admin': user.is_admin, 'is_active_status': user.is_active_status,
            'is_subscribed': user.is_subscribed, 'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'role': user.role
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'User')).start()

        flash('Account created! You can now login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email').lower()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=True)
            log_audit(db, user.id, "User Login")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route("/logout")
def logout():
    uid = current_user.id if current_user.is_authenticated else None
    if uid:
        log_audit(db, uid, "User Logout")
    logout_user()
    return redirect(url_for('home'))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        users = User.query.all()
        orders = Order.query.order_by(Order.created_at.desc()).all()
        tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
        leads = Lead.query.order_by(Lead.created_at.desc()).all()
        portfolio = PortfolioItem.query.all()
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
        profile_reqs = ProfileRequest.query.order_by(ProfileRequest.created_at.desc()).all()
        
        # Stats
        stats = {
            'total_users': len(users),
            'total_orders': len(orders),
            'pending_tickets': SupportTicket.query.filter_by(status='Open').count(),
            'total_leads': len(leads)
        }
        
        return render_template('dashboard.html', users=users, orders=orders, tickets=tickets, leads=leads, 
                               portfolio=portfolio, jobs=jobs, audit_logs=audit_logs, stats=stats, profile_requests=profile_reqs)
    else:
        user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        user_tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all()
        notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        return render_template('dashboard.html', orders=user_orders, tickets=user_tickets, notifications=notifs)

@app.route("/order/new", methods=['POST'])
@login_required
def new_order():
    service_id = request.form.get('service_id')
    details = request.form.get('details')
    
    service = Service.query.get(service_id)
    if service:
        cust_id = gen_order_id()
        try:
            order = Order(custom_order_id=cust_id, user_id=current_user.id, service_id=service.id, 
                          service_name=service.title, details=details)
            db.session.add(order)
            db.session.commit()
            
            # Add Initial Timeline
            tl = OrderTimeline(order_id=order.id, action_type="Order Submitted", performed_by=current_user.username, note="Awaiting review.")
            db.session.add(tl)
            db.session.commit()
            
            # Background Sync to Sheets
            sync_data = {
                'id': order.id,
                'custom_order_id': cust_id, 
                'user_id': current_user.id, 
                'service_name': service.title, 
                'details': details,
                'status': 'Submitted'
            }
            threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Order')).start()
        except Exception as e:
            db.session.rollback()
            print(f"Order Storage Error: {e}")
            flash('Error creating order.', 'danger')
            return redirect(url_for('home'))

        # Notify Admin
        admin = User.query.filter_by(is_admin=True, role='Super Admin').first()
        if admin:
            add_notification(admin.id, "New Order Received", f"Order {cust_id} from {current_user.username}", 
                             link=url_for('dashboard', _anchor=f'order-{order.id}'),
                             template='emails/admin_alert.html',
                             event_type='New Order',
                             event_details=f"Service: {service.title} | ID: {cust_id}",
                             user_name=current_user.username,
                             user_email=current_user.email)
        
        flash('Order placed successfully.', 'success')
        return redirect(url_for('dashboard'))
    return redirect(url_for('home'))

@app.route("/ticket/new", methods=['POST'])
@login_required
def new_ticket():
    order_id = request.form.get('order_id')
    subject = request.form.get('subject')
    desc = request.form.get('description')
    priority = request.form.get('priority', 'Medium')
    
    if subject and desc:
        with app.app_context():
            try:
                ticket = SupportTicket(user_id=current_user.id, order_id=order_id, subject=subject, description=desc, priority=priority,
                                    custom_ticket_id=gen_ticket_id())
                db.session.add(ticket)
                db.session.commit()
                
                # Parallel Sync to Sheets
                sync_data = {
                    'id': ticket.id,
                    'custom_ticket_id': ticket.custom_ticket_id,
                    'user_id': current_user.id,
                    'order_id': order_id,
                    'subject': subject,
                    'description': desc,
                    'priority': priority,
                    'status': 'Open'
                }
                threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Ticket')).start()
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

@app.route("/jobs")
def jobs():
    # Show all posted jobs
    all_jobs = Job.query.filter_by(status='Posted').order_by(Job.posted_at.desc()).all()
    # Categorize
    categories = JobCategory.query.all()
    return render_template('jobs.html', jobs=all_jobs, categories=categories)

@app.route("/job/<int:id>")
def job_detail(id):
    job = Job.query.get_or_404(id)
    return render_template('job_detail.html', job=job)

@app.route("/job/share/<int:id>")
def job_share(id):
    job = Job.query.get_or_404(id)
    job.share_count += 1
    db.session.commit()
    # Sync this update to sheets in background
    sync_data = {'id': job.id, 'share_count': job.share_count}
    threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Job')).start()
    return jsonify({'status': 'success', 'shares': job.share_count})

@app.route("/portfolio")
def portfolio_all():
    items = PortfolioItem.query.filter_by(active=True).all()
    return render_template('portfolio.html', items=items)

# Admin Module Action Endpoints
@app.route("/admin/order/update", methods=['POST'])
@login_required
def update_order():
    if not current_user.is_admin: return redirect(url_for('home'))
    oid = request.form.get('order_id')
    status = request.form.get('status')
    note = request.form.get('note')
    
    order = Order.query.get(oid)
    if order:
        order.status = status
        tl = OrderTimeline(order_id=order.id, action_type=f"Status: {status}", performed_by=current_user.username, note=note)
        db.session.add(tl)
        db.session.commit()
        
        # Notify User
        add_notification(order.user_id, "Order Update", f"Order {order.custom_order_id} is now {status}.", 
                         link=url_for('dashboard', _anchor=f'order-{order.id}'),
                         template='emails/order_update.html',
                         order_id=order.custom_order_id,
                         status=status,
                         note=note)
        
        # Sync to Sheets
        sync_data = {'id': order.id, 'status': status}
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Order')).start()
        
        flash('Order updated.', 'success')
    return redirect(url_for('dashboard', _anchor='tab-orders'))

@app.route("/admin/portfolio/action", methods=['POST'])
@login_required
def admin_portfolio_action():
    if not current_user.is_admin: return redirect(url_for('home'))
    action = request.form.get('action')
    title = request.form.get('title')
    client = request.form.get('client')
    cat = request.form.get('category')
    image_url = request.form.get('image_url')
    video_url = request.form.get('video_url')
    ext_link = request.form.get('external_link')
    
    item = None
    if action == 'add':
        item = PortfolioItem(title=title, client_name=client, category=cat, image_url=image_url, video_url=video_url, external_link=ext_link)
        db.session.add(item)
    elif action == 'edit':
        iid = request.form.get('item_id')
        item = PortfolioItem.query.get(iid)
        if item:
            item.title = title
            item.client_name = client
            item.category = cat
            item.image_url = image_url
            item.video_url = video_url
            item.external_link = ext_link
    elif action == 'delete':
        iid = request.form.get('item_id')
        item = PortfolioItem.query.get(iid)
        if item: 
            # Delete from sheets
            sync_data = {'id': item.id, '_delete': True}
            threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Portfolio')).start()
            db.session.delete(item)
    
    db.session.commit()
    
    # Sync to Sheets
    if action in ['add', 'edit'] and item:
        sync_data = {
            'id': item.id,
            'title': item.title,
            'client_name': item.client_name,
            'category': item.category,
            'image_url': item.image_url,
            'video_url': item.video_url,
            'external_link': item.external_link,
            'active': item.active
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Portfolio')).start()

    flash(f'Portfolio item {action}ed.', 'success')
    return redirect(url_for('dashboard', _anchor='tab-portfolio'))

@app.route("/admin/job/action", methods=['POST'])
@login_required
def admin_job_action():
    if not (current_user.is_admin and ('jobs' in json.loads(current_user.permissions or '[]') or current_user.role == 'Super Admin')):
        return redirect(url_for('home'))
        
    action_type = request.form.get('action_type')
    title = request.form.get('title')
    desc = request.form.get('description')
    cats = request.form.get('categories') # Multi-select join
    years = request.form.get('eligible_years')
    link = request.form.get('external_link')
    
    if action_type in ['create', 'edit']:
        if not title or not desc or not cats or not link:
            flash('All fields marked * are required.', 'danger')
            return redirect(url_for('dashboard', _anchor='tab-jobs'))

    image_url = None
    file = request.files.get('image')
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Use a random prefix to prevent overlaps
        filename = f"{secrets.token_hex(4)}_{filename}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        
        # Upload to ImgBB
        image_url = upload_to_imgbb(path)
        # Delete local copy after upload
        if os.path.exists(path): os.remove(path)
        
    job = None
    if action_type == 'create':
        job = Job(title=title, description=desc, categories=cats, eligible_years=years, external_link=link, image_url=image_url, status='Posted', posted_at=datetime.now(timezone.utc))
        db.session.add(job)
    elif action_type == 'delete':
        jid = request.form.get('job_id')
        job = Job.query.get(jid)
        if job: 
             # Sync deletion
            sync_data = {'id': job.id, '_delete': True}
            threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Job')).start()
            db.session.delete(job)
    else: # edit
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
        # Check for scheduling
        sched_time = request.form.get('scheduled_time')
        if sched_time:
            job.status = 'Scheduled'
            job.scheduled_time = datetime.strptime(sched_time, '%Y-%m-%dT%H:%M')
        else:
            if action_type == 'create':
                job.status = 'Posted'
                job.posted_at = datetime.now(timezone.utc)

    db.session.commit()
    
    # Sync to Sheets
    if action_type in ['create', 'edit'] and job:
        sync_data = {
            'id': job.id,
            'title': job.title,
            'description': job.description,
            'categories': job.categories,
            'eligible_years': job.eligible_years,
            'image_url': job.image_url,
            'external_link': job.external_link,
            'status': job.status,
            'share_count': job.share_count
        }
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'Job')).start()

    return redirect(url_for('dashboard', _anchor='tab-jobs'))

@app.route("/admin/user/role", methods=['POST'])
@login_required
def admin_user_role():
    if current_user.role != 'Super Admin': return redirect(url_for('home'))
    uid = request.form.get('user_id')
    new_role = request.form.get('role')
    perms = request.form.getlist('permissions[]') # List of perms
    
    user = User.query.get(uid)
    if user:
        user.role = new_role
        user.is_admin = True if new_role in ['Admin', 'Limited Admin', 'Super Admin'] else False
        user.permissions = json.dumps(perms)
        db.session.commit()
        
        # Sync update to sheets
        sync_data = {'id': user.id, 'role': new_role, 'is_admin': user.is_admin, 'permissions': user.permissions}
        threading.Thread(target=sync_to_google_sheets, args=(sync_data, 'User')).start()
        
        flash(f'Permissions updated for {user.username}.', 'info')
    return redirect(url_for('dashboard', _anchor='tab-users'))

@app.route("/contact", methods=['POST'])
def handle_contact():
    name = request.form.get('name')
    email = request.form.get('email').lower()
    phone = request.form.get('phone')
    service = request.form.get('service')
    msg = request.form.get('message')
    
    if not name or not email or not service or not msg:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('home', _anchor='contact'))

    # Parallel Storage: Database & Sheets
    try:
        new_lead = Lead(full_name=name, email=email, phone=phone, service=service, message=msg)
        db.session.add(new_lead)
        db.session.commit()
        
        # Standardized Sync Data
        data = {
            'id': new_lead.id,
            'full_name': name,
            'email': email,
            'phone': phone,
            'service': service,
            'message': msg
        }
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
        add_notification(admin.id, "New Lead Inquiry", f"From {name} ({service})", 
                         link=url_for('dashboard', _anchor='tab-leads'),
                         template='emails/admin_alert.html',
                         event_type='New Inquiry',
                         event_details=f"Service: {service} | Message: {msg[:100]}...",
                         user_name=name,
                         user_email=email)
    
    flash('Thank you for your message! We will get back to you shortly.', 'success')
    return redirect(url_for('home', _anchor='contact'))

@app.route("/api/v1/jobs")
def api_jobs():
    jobs = Job.query.filter_by(status='Posted').all()
    data = [{
        'id': j.id, 'title': j.title, 
        'cats': j.categories.split(';'), 
        'years': j.eligible_years.split(';'),
        'link': j.external_link,
        'img': j.image_url
    } for j in jobs]
    return jsonify(data)

# Helper generators
def gen_order_id():
    return f"RVTSORD{secrets.token_hex(4).upper()}"

def gen_ticket_id():
    return f"RVTSTKT{secrets.token_hex(4).upper()}"

def gen_user_id():
    return f"RVTSUSER{secrets.token_hex(3).upper()}"

if __name__ == '__main__':
    # Force use of 10000 for Render compatibility
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
