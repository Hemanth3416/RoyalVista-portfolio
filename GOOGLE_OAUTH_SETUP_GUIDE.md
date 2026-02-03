# Google OAuth 2.0 Integration Guide for RoyalVista Tech Solutions

## Complete Setup Guide - Step by Step

---

## Phase 1: Google Cloud Console Setup (15 minutes)

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. **Project Name**: `RoyalVista-Tech-Solutions`
4. Click **"Create"**
5. Wait for the project to be created (notification will appear)

---

### Step 2: Configure OAuth Consent Screen

1. In the left sidebar, go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (allows anyone with a Google account to sign in)
3. Click **"Create"**

**Fill in the required fields:**

- **App name**: `RoyalVista Tech Solutions`
- **User support email**: `royalvistatechsolutions@gmail.com`
- **App logo** (optional): Upload your logo (120x120px PNG)
- **Application home page**: `https://yourdomain.com` (or `http://localhost:5005` for testing)
- **Authorized domains**: Add your domain (e.g., `yourdomain.com`)
- **Developer contact email**: `royalvistatechsolutions@gmail.com`

4. Click **"Save and Continue"**

---

### Step 3: Add Scopes (Optional - Can Skip for Now)

**Note**: The basic scopes (`openid`, `email`, `profile`) are automatically included. You can skip this step for initial testing.

If you want to explicitly add them:
1. Click **"Add or Remove Scopes"**
2. Filter/search for these scopes:
   - `.../auth/userinfo.email` - View email address
   - `.../auth/userinfo.profile` - View basic profile info
3. Click **"Update"** → **"Save and Continue"**

**Important**: These are non-sensitive scopes and don't require Google verification.

---

### Step 4: Test Users (SKIP THIS - Not Required!)

**You can skip this step entirely!** 

Google changed their policy - you no longer need to add test users for external apps during development. Your app will work with any Google account, but will show an "unverified app" warning (which is normal for development).

**If you still want to add test users** (optional):
1. Click **"Add Users"**
2. Add emails like: `royalvistatechsolutions@gmail.com`
3. Click **"Save and Continue"**

**Just click "Back to Dashboard"** to proceed.

---

### Step 5: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. **Application type**: Select **"Web application"**
4. **Name**: `RoyalVista Web Client`

**Configure URLs:**

**Authorized JavaScript origins** (for frontend):
```
http://localhost:5005
http://127.0.0.1:5005
https://yourdomain.com
```

**Authorized redirect URIs** (for backend callback):
```
http://localhost:5005/auth/google/callback
http://127.0.0.1:5005/auth/google/callback
https://yourdomain.com/auth/google/callback
```

5. Click **"Create"**

---

### Step 6: Save Your Credentials

You'll see a popup with:
- **Client ID**: `123456789-abcdefg.apps.googleusercontent.com`
- **Client Secret**: `GOCSPX-xxxxxxxxxxxxx`

**IMPORTANT**: 
- Download the JSON file (click "Download JSON")
- **Never commit these to GitHub!**
- Store them securely

---

## Phase 2: Backend Implementation (Python/Flask)

### Step 1: Install Required Packages

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

### Step 2: Update Your `.env` File

Create or update `/local/My_Works/personal-portfolio/.env`:

```env
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret-here
GOOGLE_REDIRECT_URI=http://localhost:5005/auth/google/callback

# For production, change to:
# GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
```

### Step 3: Update `app.py` - Add OAuth Configuration

Add this after your imports (around line 30):

```python
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests

# Google OAuth Config
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5005/auth/google/callback')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
```

### Step 4: Update the `/login/google` Route

Replace the existing mock Google login route (around line 325) with:

```python
@app.route("/login/google")
def google_login():
    # Generate random state for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
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
    if state != session.get('oauth_state'):
        flash('Invalid state parameter. Please try again.', 'danger')
        return redirect(url_for('login'))
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('Authorization failed. Please try again.', 'danger')
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
        
        if not user:
            # Create new user
            user = User(
                username=name,
                email=email,
                google_id=google_id,
                password=bcrypt.generate_password_hash(secrets.token_urlsafe(32)).decode('utf-8'),  # Random password
                role='Client',
                is_admin=False,
                permissions='[]'
            )
            db.session.add(user)
            db.session.commit()
            
            # Send welcome notification
            add_notification(
                user.id,
                "Welcome to RoyalVista!",
                "Your account has been created successfully via Google Sign-In.",
                link=url_for('dashboard'),
                template='emails/welcome.html'
            )
            
            flash('Account created successfully! Welcome to RoyalVista!', 'success')
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
```

---

## Phase 3: Frontend Integration

### Update `templates/login.html`

Find the Google login button (around line 40-50) and update it:

```html
<!-- Google Sign-In Button -->
<a href="{{ url_for('google_login') }}" class="google-btn" style="display: flex; align-items: center; justify-content: center; gap: 10px; background: #fff; color: #333; padding: 0.8rem; border-radius: 8px; text-decoration: none; border: 1px solid #ddd; transition: 0.3s; margin-bottom: 1rem;">
    <svg width="20" height="20" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
    <span>Continue with Google</span>
</a>
```

---

## Phase 4: Security Checklist

### ✅ Before Going Live:

1. **Environment Variables**: Ensure `.env` is in `.gitignore`
2. **HTTPS Only**: Google OAuth requires HTTPS in production
3. **Update Redirect URIs**: Change from `localhost` to your actual domain
4. **Verify Scopes**: Only request necessary permissions
5. **Session Security**: Use secure session cookies:

```python
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

6. **Rate Limiting**: Add rate limiting to prevent abuse
7. **Error Handling**: Never expose sensitive errors to users

---

## Phase 5: Testing

### Local Testing Steps:

1. Start your server: `python app.py`
2. Go to: `http://localhost:5005/login`
3. Click "Continue with Google"
4. Sign in with your Google account
5. You should be redirected to the dashboard

### Troubleshooting:

**Error: "redirect_uri_mismatch"**
- **Cause**: The redirect URI in your code doesn't match Google Console
- **Solution**: 
  - Go to Google Console → Credentials → Your OAuth Client
  - Check "Authorized redirect URIs"
  - Make sure `http://localhost:5005/auth/google/callback` is listed EXACTLY
  - Include the protocol (`http://`)
  - No trailing slash

**Error: "invalid_client"**
- **Cause**: Wrong Client ID or Secret
- **Solution**:
  - Check your `.env` file has correct values
  - Verify no extra spaces or quotes
  - Make sure environment variables are loaded: `print(GOOGLE_CLIENT_ID)` in app.py

**Error: "access_denied"**
- **Cause**: User clicked "Cancel" or app not verified
- **Solution**: This is normal during development. Click "Advanced" → "Go to RoyalVista (unsafe)" on the warning screen

**Error: "App is not verified" warning**
- **Cause**: Your app is in testing mode
- **Solution**: This is NORMAL for development. Users can still proceed by clicking "Advanced"

**Error: "Can't add scopes" or "Scopes not available"**
- **Solution**: You don't need to manually add scopes! They're included automatically. Just skip Step 3.

**Error: "Missing required packages"**
- **Solution**: Run `pip install google-auth google-auth-oauthlib google-auth-httplib2 requests`

**Server not starting after adding OAuth code**
- **Solution**: Check for syntax errors, make sure all imports are at the top of app.py

---

## Phase 6: Production Deployment

### When deploying to production:

1. **Update Google Console**:
   - Add production domain to Authorized origins
   - Add production callback URL to Redirect URIs

2. **Update `.env` on server**:
```env
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
```

3. **Publish OAuth Consent Screen** (optional):
   - Go to OAuth consent screen
   - Click "Publish App"
   - This removes the "unverified app" warning

---

## Quick Reference

### Important URLs:
- **Google Cloud Console**: https://console.cloud.google.com/
- **OAuth Playground** (for testing): https://developers.google.com/oauthplayground/

### Required Environment Variables:
```
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
```

### Key Files to Update:
1. `.env` - Add credentials
2. `app.py` - Add OAuth routes
3. `templates/login.html` - Update button

---

## Support

If you encounter issues:
1. Check Google Cloud Console logs
2. Verify all URLs match exactly
3. Ensure HTTPS in production
4. Check that test users are added (during development)

**Need help?** The error messages from Google are usually very specific about what's wrong.

---

**Created for RoyalVista Tech Solutions**
**Last Updated**: January 2026
