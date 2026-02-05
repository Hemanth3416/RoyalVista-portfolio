
import os
from app import app, db
from rebuild_sheets import rebuild

def reset_all_data():
    """
    1. Drops all local database tables.
    2. Recreates all tables.
    3. Runs rebuild_sheets.py to wipe and re-initialize Google Sheets.
    """
    print("WARNING: This will DELETE ALL DATA from both the database and Google Sheets.")
    
    with app.app_context():
        # 1. Drop All
        print("Dropping all database tables...")
        db.drop_all()
        print("Tables dropped.")
        
        # 2. Create All
        print("Creating all database tables...")
        db.create_all()
        print("Tables created.")
        
        # 3. Trigger Maintenance (Seeding)
        # We can simulate the maintenance thread logic to ensure default admin/services exist
        from models import User, Service, JobCategory
        
        print("Seeding default data...")
        if not User.query.filter_by(role='Super Admin').first():
             from flask_bcrypt import Bcrypt
             bcrypt = Bcrypt(app)
             hashed_pw = bcrypt.generate_password_hash('RoyalVista@2026').decode('utf-8')
             # Use generic admin details
             db.session.add(User(
                 username='RoyalVista Admin', 
                 email='royalvistatechsolutions@gmail.com', 
                 password=hashed_pw, 
                 is_admin=True, 
                 role='Super Admin', 
                 permissions='["jobs", "newsletters", "chatbot", "users"]', 
                 phone_number="+1234567890",
                 custom_user_id="RVTSADMIN001"
             ))
        
        if not Service.query.first():
             db.session.add_all([
                Service(title='Web Design', description='Professional website design and development.', icon_class='fas fa-desktop'),
                Service(title='Logo Design', description='Unique and memorable logo creation.', icon_class='fas fa-pen-nib'),
                Service(title='Video Editing', description='High-quality video editing for various platforms.', icon_class='fas fa-video'),
                Service(title='Thumbnails', description='Eye-catching thumbnails for videos and content.', icon_class='fas fa-image'),
                Service(title='Posters & Ads', description='Creative poster and advertisement designs.', icon_class='fas fa-ad'),
                Service(title='Wedding Invitations', description='Elegant and personalized wedding invitation designs.', icon_class='fas fa-heart'),
                Service(title='SEO Services', description='Search Engine Optimization to improve online visibility.', icon_class='fas fa-search'),
                Service(title='Social Media Marketing', description='Strategies and content for effective social media presence.', icon_class='fas fa-share-alt'),
                Service(title='Others', description='Custom design and digital solutions tailored to your needs.', icon_class='fas fa-ellipsis-h')
            ])

        if not JobCategory.query.first():
             db.session.add_all([
                 JobCategory(name='Web Development'),
                 JobCategory(name='Graphic Design'),
                 JobCategory(name='Video Production'),
                 JobCategory(name='Digital Marketing'),
                 JobCategory(name='Content Creation'),
                 JobCategory(name='UI/UX Design'),
                 JobCategory(name='Mobile App Development'),
                 JobCategory(name='Data Entry'),
                 JobCategory(name='Customer Service'),
                 JobCategory(name='Other')
             ])
        
        db.session.commit()
        print("Seeding complete.")

    # 4. Rebuild Sheets
    print("Rebuilding Google Sheets...")
    rebuild()
    print("System Reset Complete.")

if __name__ == "__main__":
    reset_all_data()
