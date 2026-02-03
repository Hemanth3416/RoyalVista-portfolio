from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True) 
    password = db.Column(db.String(60), nullable=True) 
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    custom_user_id = db.Column(db.String(20), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_status = db.Column(db.Boolean, default=True) # Renamed to avoid conflict with UserMixin.is_active
    is_subscribed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='client', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    tickets = db.relationship('SupportTicket', backref='user', lazy=True)
    
    # Permissions (JSON-encoded list of permissions like ['jobs', 'newsletters', 'chatbot'])
    permissions = db.Column(db.Text, nullable=True) 
    role = db.Column(db.String(20), default='Client') # Super Admin, Admin, Limited Admin, Client
    profile_edited_count = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class ProfileRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    new_username = db.Column(db.String(50), nullable=True)
    new_phone = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=False) # Reason for change
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('profile_requests', lazy=True))

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon_class = db.Column(db.String(50), nullable=False, default='fas fa-cube')
    active = db.Column(db.Boolean, default=True)

class PortfolioItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    client_name = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=False) # web, logo, thumbnails, posters, video, student
    image_url = db.Column(db.String(200), nullable=True)
    video_url = db.Column(db.String(200), nullable=True)
    external_link = db.Column(db.String(200), nullable=True)
    active = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_order_id = db.Column(db.String(20), unique=True, nullable=False) # RVTSXXXXXXXX
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    service_name = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Submitted')
    output_url = db.Column(db.String(200), nullable=True)
    output_type = db.Column(db.String(50), nullable=True) # image, video, link
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    timeline = db.relationship('OrderTimeline', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderTimeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    performed_by = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    note = db.Column(db.Text, nullable=True)
    file_url = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(20), nullable=True) # image, video, document

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    custom_ticket_id = db.Column(db.String(20), unique=True, nullable=True) # RVTSTICKETXXXX
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True) # Linked Order
    order = db.relationship('Order', backref='support_tickets')
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='Medium') # Low, Medium, High
    status = db.Column(db.String(20), default='Open') # Open, In Progress, Resolved, Closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ScheduledEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    recipients = db.Column(db.Text, nullable=False) # JSON-encoded list of emails
    scheduled_time = db.Column(db.DateTime, nullable=True) # If null, send immediately
    status = db.Column(db.String(20), default='Scheduled') # Draft, Scheduled, Sent, Failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    error_log = db.Column(db.Text, nullable=True)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    categories = db.Column(db.Text, nullable=False) # Semi-colon separated categories
    eligible_years = db.Column(db.String(100), nullable=False) # e.g. "2024;2025"
    image_url = db.Column(db.String(200), nullable=True)
    external_link = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='Draft') # Draft, Scheduled, Posted
    scheduled_time = db.Column(db.DateTime, nullable=True)
    share_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posted_at = db.Column(db.DateTime, nullable=True)

class JobCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class JobSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('job_category.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('job_subscriptions', cascade="all, delete-orphan"))
    category = db.relationship('JobCategory', backref=db.backref('subscriptions', cascade="all, delete-orphan"))

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    service = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SiteContent(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=False)
