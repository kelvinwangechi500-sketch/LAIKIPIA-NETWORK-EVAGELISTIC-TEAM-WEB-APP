# 🚀 NET Platform — Deployment Guide
## Android App + Online Deployment

---

## 📋 WHAT'S IN THIS ZIP

```
NET_Platform/
├── app.py              ← Main Flask app (updated for deployment)
├── config.py           ← Auto-switches SQLite (local) / PostgreSQL (online)
├── extensions.py       ← Flask extensions
├── requirements.txt    ← All Python packages
├── Procfile            ← Tells Railway how to run the app
├── runtime.txt         ← Python version for Railway
├── .env                ← Your local environment variables
├── .env.example        ← Template for reference
├── .gitignore          ← Files excluded from GitHub
├── models/             ← Database models (fixed)
├── routes/             ← All page routes
├── services/           ← AI features (OCR, transcription)
├── static/
│   ├── css/main.css
│   ├── js/main.js
│   ├── img/logo.png
│   ├── manifest.json   ← NEW: Makes it installable as Android app
│   └── sw.js           ← NEW: Service worker for offline support
├── templates/          ← All HTML pages (all fixed)
├── instance/           ← SQLite database stored here (auto-created)
└── uploads/            ← User uploaded files (auto-created)
```

---

## 💻 STEP 1 — Run Locally in VSCode

### 1a. Open the folder
Unzip → open VSCode → File → Open Folder → select `NET_Platform`

### 1b. Create virtual environment
```bash
python -m venv venv
```

### 1c. Activate it
```bash
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### 1d. Install packages
```bash
pip install -r requirements.txt
```

### 1e. Run the app
```bash
python app.py
```

### 1f. Open browser
Go to: **http://localhost:5000**

Login: `admin@net.org` / `Admin@1234`

---

## 🌍 STEP 2 — Deploy Online (Railway — FREE)

### 2a. Install Git
Download from **https://git-scm.com** and install it.
Restart VSCode after installing.

### 2b. Create GitHub account
Go to **https://github.com** and sign up free.

### 2c. Push your project to GitHub

In VSCode terminal (with venv activated):

```bash
git init
git add .
git commit -m "NET Platform - ready for deployment"
```

Then go to **https://github.com/new** and:
- Repository name: `NET_Platform`
- Keep it **Private** (recommended)
- Click **Create repository**

GitHub will show you commands — run them in your terminal:
```bash
git remote add origin https://github.com/YOUR-USERNAME/NET_Platform.git
git branch -M main
git push -u origin main
```

### 2d. Deploy on Railway

1. Go to **https://railway.app**
2. Click **"Start a New Project"**
3. Sign up / login with your **GitHub account**
4. Click **"Deploy from GitHub repo"**
5. Select **NET_Platform**
6. Click **"Deploy Now"**

Wait 2–3 minutes for the build to finish.

### 2e. Add Environment Variables on Railway

In your Railway project:
1. Click on your service (the box shown)
2. Click **"Variables"** tab
3. Click **"Add Variable"** and add these one by one:

| Variable Name | Value |
|---|---|
| `SECRET_KEY` | `NET-EVT-AnyLongRandomString-2024!` |
| `FLASK_ENV` | `production` |
| `OPENAI_API_KEY` | Your OpenAI key (or leave blank) |

### 2f. Get your live URL

1. Click **"Settings"** tab in Railway
2. Click **"Networking"**
3. Click **"Generate Domain"**

You get a URL like:
```
https://net-platform-production.up.railway.app
```

✅ **Your platform is now live on the internet!**

Share this URL with your team.

---

## 📱 STEP 3 — Install as Android App (No App Store!)

Once your platform is online, members can install it as an Android app:

### How members install it:

1. Open **Chrome browser** on their Android phone
2. Visit your Railway URL (e.g. `https://net-platform-production.up.railway.app`)
3. Login with their credentials
4. Chrome shows a popup: **"Add NET Platform to Home Screen"**
   - If popup doesn't appear: tap the **3 dots menu** (top right) → **"Add to Home Screen"**
5. Tap **"Add"**

✅ The NET Platform icon appears on their home screen like a real app!
✅ Opens fullscreen with no browser address bar
✅ Works offline for basic browsing
✅ Chat messages sync automatically when back online

---

## 🔄 STEP 4 — Updating the App After Changes

When you make changes to your code locally:

```bash
git add .
git commit -m "describe what you changed"
git push
```

Railway **automatically redeploys** within 2 minutes. ✅

---

## 🗄️ STEP 5 — Database (Production)

Railway provides a free **PostgreSQL** database. To use it:

1. In Railway project → click **"New"** → **"Database"** → **"PostgreSQL"**
2. Click on the PostgreSQL service → **"Variables"**
3. Copy the `DATABASE_URL` value
4. Add it as a variable to your main service:
   - Variable: `DATABASE_URL`
   - Value: (paste the PostgreSQL URL)

The app automatically uses PostgreSQL when `DATABASE_URL` is set. ✅

---

## 🔑 Login Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@net.org | Admin@1234 |

⚠️ **Change admin password immediately after first login!**

---

## 🤖 AI Features (Optional)

To enable OCR attendance and voice transcription:

1. Get a key from **https://platform.openai.com/api-keys**
2. Add it to Railway Variables: `OPENAI_API_KEY` = `sk-your-key`
3. Redeploy

Without it, all other features work perfectly.

---

## 🆘 Common Issues

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with venv active |
| Login redirect loop | Clear browser cookies and try again |
| Railway build fails | Check the build logs — usually a package issue |
| Mic not working | Use Chrome/Edge. Must be HTTPS in production (Railway provides this) |
| Members can't install app | They must use Chrome on Android, not Samsung Internet |

---

## 📞 Support

If Railway build fails, check the **"Deploy Logs"** tab in Railway for the exact error.

*Network Evangelistic Team Management Platform ✝️*
