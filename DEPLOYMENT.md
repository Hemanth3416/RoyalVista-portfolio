# 🛠️ Tools Installation & Deployment Steps (Render.com)

## 🚀 STEP 1: Preparation
1. **GitHub Repository:**
   - Create a private or public repository on GitHub.
   - Upload all files from this project.

2. **Google Cloud Console:**
   - Go to [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials).
   - Update your **Authorized Redirect URIs** to include your live Render URL:
     `https://your-app-name.onrender.com/auth/google/callback`

---

## 🚀 STEP 2: Free Hosting on Render
Render is the best alternative for free Python hosting.

1. **Connect to Render:**
   - Go to [Render.com](https://dashboard.render.com/) and create a free account.
   - Click **"New +"** -> **"Web Service"**.
   - Connect your GitHub account and select this repository.

2. **Configure Settings:**
   - **Language:** `Docker`
   - **Instance Type:** Select **"Free"**.

3. **Add Environment Variables:**
   Click **"Advanced"** and add these keys:
   - `GOOGLE_CLIENT_ID`: [PASTE_FROM_CONVERSATION]
   - `GOOGLE_CLIENT_SECRET`: [PASTE_FROM_CONVERSATION]
   - `GOOGLE_REDIRECT_URI`: [PASTE_YOUR_RENDER_URL]/auth/google/callback
   - `SECRET_KEY`: [GENERATE_A_RANDOM_STRING]
   - `MAIL_USERNAME`: royalvistatechsolutions@gmail.com
   - `MAIL_PASSWORD`: [PASTE_APP_PASSWORD_FROM_CONVERSATION]
   - `GOOGLE_DRIVE_FOLDER_ID`: [PASTE_FROM_GOOGLE_DRIVE_URL]

4. **Secret Files:**
   - Add a Secret File named `credentials.json` and paste the contents of your local `credentials.json`.

5. **Deploy:**
   - Click **"Create Web Service"**.

---

## 🔒 Secrets & Security
- Never push `.env` or `credentials.json` to GitHub (Handled by `.gitignore`).
- Use Render built-in "Environment Variables" for production secrets.

## ⚠️ Database Note
SQLite databases on the Free Tier are cleared on every restart. For long-term data, ensure Google Sheets synchronization is active.
