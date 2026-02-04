# RoyalVista Tech Solutions - Automation Setup Guide

To enable email notifications and Google Sheets integration, you need to configure a few secure credentials.

## 1. Gmail Automation (SMTP)

We use Gmail to send automated emails. Since normal passwords don't work for apps anymore due to security, you need an **App Password**.

1.  **Go to Google Security**: Visit [https://myaccount.google.com/security](https://myaccount.google.com/security).
2.  **Enable 2-Step Verification**: If it's not on, enable it. this is required.
3.  **Generate App Password**:
    *   Search for "App Passwords" in the top search bar.
    *   Create a new one named `RoyalVista Website`.
    *   Google will give you a 16-character code (e.g., `abcd efgh ijkl mnop`).
4.  **Save Credentials**:
    *   Create a file named `.env` in your project folder (use `.env.example` as a reference).
    *   Add your details:
        ```ini
        # .env
        MAIL_USERNAME=royalvistatechsolutions@gmail.com
        MAIL_PASSWORD=your_16_char_app_password
        ```

## 2. Google Sheets Integration

We use a "Service Account" to write data securely to your Google Sheet without manual login.

1.  **Create Service Account**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a **New Project** (e.g., "RoyalVista Portfolio").
    *   Go to **APIs & Services** > **Dashboard** > **Enable APIs and Services**.
    *   Enable **Google Sheets API** and **Google Drive API**.
    *   Go to **Credentials** > **Create Credentials** > **Service Account**.
    *   Name it (e.g., `sheet-updater`) and finish.
2.  **Get Key File**:
    *   Click on your new service account email (e.g., `sheet-updater@...`).
    *   Go to **Keys** tab > **Add Key** > **Create new key** > **JSON**.
    *   Download the file, rename it to `credentials.json`, and put it in your project folder.
3.  **Setup the Sheet**:
    *   Create a new Google Sheet named `RoyalVista_DB`.
    *   **Share** the sheet with the `client_email` found inside your `credentials.json`. Give it **Editor** access.
    *   **Add Headers** to the first row of "Sheet1" exactly in this order:
        *   `Full Name`
        *   `Email`
        *   `Phone`
        *   `Service`
        *   `Message`
        *   `Type` (Lead/Order)
        *   `Timestamp`

## 3. Image Storage (ImgBB)

We use ImgBB to store images permanently (since Render deletes local files on restart).

1.  **Get API Key**: Go to [api.imgbb.com](https://api.imgbb.com/) and create a free account to get your API key.
2.  **Add to Config**: Add `IMGBB_API_KEY=your_key_here` to your `.env` or Render environment variables.

## 4. Install Requirements

Ensure you have the necessary libraries installed by running this command in your terminal:

```bash
pip install gspread google-auth python-dotenv
```
