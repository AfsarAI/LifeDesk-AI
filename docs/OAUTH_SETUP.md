# Google OAuth 2.0 Setup Guide

This guide walks through creating real Google OAuth 2.0 credentials in Google Cloud Console so LifeDesk AI can connect to **Gmail** and **Google Calendar**.

---

## 1. Create a Google Cloud Project

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project selector at the top and choose **New Project**.
3. Name it `LifeDesk AI` (or similar) and click **Create**.

---

## 2. Enable Required Google APIs

1. Navigate to **APIs & Services → Library** ([Google API Library](https://console.cloud.google.com/apis/library)).
2. Search for **Gmail API** and click **Enable**.
3. Search for **Google Calendar API** and click **Enable**.

---

## 3. Configure the OAuth Consent Screen & Test Users

1. Go to **Google Auth Platform → Branding / Audience** (or **APIs & Services → OAuth consent screen**).
   - Official docs: [Configure the OAuth consent screen](https://developers.google.com/workspace/guides/configure-oauth-consent).
2. Choose **External** user type (unless you are inside a Google Workspace organization and only want Internal users).
3. Fill in:
   - App name: `LifeDesk AI`
   - User support email & Developer contact email: your email address
4. Under **Audience → Test users**, add every Google email address you will use during development.
   - **Important:** While the app is in **Testing** mode, only listed test users can authorize, and refresh tokens expire every **7 days**.
5. Under **Data Access / Scopes**, add the least-privilege scopes used by LifeDesk AI:
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/gmail.readonly` *(Restricted)*
   - `https://www.googleapis.com/auth/gmail.compose` *(Restricted)*
   - `https://www.googleapis.com/auth/gmail.send` *(Restricted)*
   - `https://www.googleapis.com/auth/calendar.readonly` *(Sensitive)*
   - `https://www.googleapis.com/auth/calendar.events` *(Sensitive)*

---

## 4. Create OAuth Client Credentials

1. Navigate to **APIs & Services → Credentials** ([Create access credentials](https://developers.google.com/workspace/guides/create-credentials)).
2. Click **Create Credentials → OAuth client ID**.
3. Application type: **Web application**.
4. Name: `LifeDesk AI Local Dev`.
5. Under **Authorized JavaScript origins**, add:
   - `http://localhost:5173`
6. Under **Authorized redirect URIs**, add the exact backend callback URL:
   - `http://localhost:8000/api/integrations/google/callback`
7. Click **Create** and copy the **Client ID** and **Client Secret**.

---

## 5. Configure `backend/.env`

Generate a Fernet encryption key for resting tokens:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add the values to `backend/.env` (never commit `.env` to Git):
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/google/callback
TOKEN_ENCRYPTION_KEY=your-generated-fernet-key
FRONTEND_URL=http://localhost:5173
```

---

## 6. Run Locally & Test Connections

1. Start the backend (`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`) and frontend (`npm run dev`).
2. Open `http://localhost:5173` and click **Integrations** in the left sidebar.
3. Click **Connect Gmail** or **Connect Google Calendar** (or **Connect All Google Services**).
4. Complete the Google consent screen; you will be redirected back to `http://localhost:5173/?page=integrations&oauth=connected`.
5. Test **Gmail** in Chat:
   - *"List my 5 most recent emails."*
   - *"Search emails about internship."*
6. Test **Calendar** in Chat:
   - *"What is on my calendar today?"*
   - *"Am I free tomorrow at 3 PM?"*

---

## 7. Google Scope Classifications & Production Verification

Google classifies OAuth scopes into three tiers ([Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy)):

| Scope | Classification | Production Verification Requirement |
|---|---|---|
| `openid`, `userinfo.email` | Non-sensitive | Basic app branding check only |
| `calendar.readonly`, `calendar.events` | **Sensitive** | Google Sensitive Scope Verification (privacy policy, terms, YouTube OAuth demo video) |
| `gmail.readonly`, `gmail.compose`, `gmail.send` | **Restricted** | Google Restricted Scope Verification **plus annual independent CASA (Cloud App Security Assessment) Tier 2/3 security audit** |

Reference documentation:
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [OAuth 2.0 Scopes for Google APIs](https://developers.google.com/identity/protocols/oauth2/scopes)
- [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy)
