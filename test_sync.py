
import os
import json
from utils import sync_to_google_sheets

# Full Test data matching the DB User model structure
test_data = {
    'id': 1,
    'username': 'Test User',
    'email': 'test_full_v1@example.com',
    'phone_number': '1234567890',
    'password': 'hashed_password_example',
    'google_id': 'google_123',
    'custom_user_id': 'RVTSUSER000001',
    'is_admin': False,
    'is_active_status': True,
    'is_subscribed': True,
    'created_at': '2026-02-03 22:15:00',
    'permissions': '[]',
    'role': 'Client',
    'profile_edited_count': 0
}

print("Starting Full Sync Test...")
result = sync_to_google_sheets(test_data, 'User')
print(f"Sync Result: {result}")
