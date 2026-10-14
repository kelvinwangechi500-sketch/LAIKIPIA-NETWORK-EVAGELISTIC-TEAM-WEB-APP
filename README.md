# NET Platform

**Network Evangelistic Team — Management Platform**

A Flask web app for managing members, attendance, meeting minutes, announcements, and real-time team chat. Includes role-based access control and optional email services.

---

## Features

| Area | Capabilities |
|------|----------------|
| **Roles** | Admin · Vice Secretary · Member |
| **Members** | Self-registration with role selection, profiles, branches |
| **Attendance** | Manual entry, image upload + OCR, exports |
| **Meetings** | Manual minutes, document uploads, date filtering, exports, sharing, and optional AI transcription |
| **Chat** | Real-time group rooms (Socket.IO), file sharing |
| **Finance** | KES transactions, receipts, admin approval, semester budgets, obligations, assets, semester and annual reports |
| **Security** | RBAC decorators, audit logs |
| **Exports** | PDF, DOCX, Excel |

The role inventory includes Admin, Vice Secretary, Treasurer, and Member.

---

## Tech stack

- **Backend:** Flask 2.3, SQLAlchemy, Flask-Login, Flask-Bcrypt, Flask-SocketIO
- **DB:** SQLite (local) · PostgreSQL (production)
- **Server:** Gunicorn gthread workers + Socket.IO threading mode
- **Python:** 3.11

---

## Quick start (local)

### 1. Prerequisites

- Python **3.11+**
- `pip` and `venv`
- (Optional) SMTP credentials for real email delivery

### 2. Clone & enter the project

```bash
cd NET_Platform-main
```

### 3. Create a virtual environment

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=change-this-to-a-long-random-string
# DATABASE_URL=          # leave empty → uses local SQLite
OPENAI_API_KEY=          # optional (meeting transcription/summary)
GROQ_API_KEY=            # optional

# Email (optional — without SMTP, verification links print in the terminal)
MAIL_SERVER=
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 6. Run the app

```bash
python app.py
```

Open **http://127.0.0.1:5000**

Default admin (seeded on first run):

| Field | Value |
|-------|--------|
| Email | `admin@net.org` |
| Password | `Admin@1234` |

> Change this password after first login.

### 7. Self-registration

1. Open **Register** on the login page.
2. Create an account (Member, Vice Secretary, or Treasurer).
3. Sign in immediately after registration. Email verification is not required.

---

## Project structure

```
NET_Platform-main/
├── app.py                 # App factory, seeding, migrations
├── config.py              # Dev / production settings
├── extensions.py          # db, login, bcrypt, socketio
├── requirements.txt
├── Procfile               # Render / Heroku process
├── runtime.txt            # Python version
├── .env.example
├── models/                # SQLAlchemy models
├── routes/                # Blueprints (auth, admin, member, vs, chat, api)
├── services/              # AI, OCR, email, export, audit
├── utils/                 # RBAC decorators
├── templates/             # Jinja2 templates by role
└── static/                # CSS, JS, logo, PWA assets
```

---

## Roles & access

| Role | Access |
|------|--------|
| **Admin** | Full control: members, branches, announcements, attendance, minutes, audit logs |
| **Vice Secretary** | Attendance upload/manual, meeting recording, minutes |
| **Treasurer** | Record KES income and expenses, receipts, budgets, obligations, assets, semester reports, annual reports |
| **Member** | Dashboard, own attendance, profile, team chat |

### Treasurer finance workflow

- All transaction amounts are stored and displayed in Kenyan shillings (KES).
- The academic reporting calendar is Semester 1: September-December and Semester 2: January-April of the following year. May-August is outside the active semester calendar.
- Transactions support income types (offerings, donations, contributions, fundraising, and other), expense categories, dates, references, payment methods, notes, and protected receipt uploads.
- The treasurer submits transactions; an administrator must approve expenses before they appear in official reports.
- Semester budgets provide category limits and planned-versus-approved-actual comparisons, including overspending indicators.
- Outstanding obligations and purchased assets can be recorded for annual reporting.
- Semester reports calculate opening balance, approved income, approved expenses, closing balance, explanations, and report status. Treasurers submit reports to leadership and administrators approve or return them.
- Annual reports combine approved transactions across both semesters and include balances, budgets, obligations, and assets.
- Leadership can export semester and annual reports as PDF or Excel. Members do not receive detailed finance access.

Finance routes are available under `/treasurer`, while administrator approvals are under `/treasurer/admin/finance`. The SQLite database is created or migrated automatically at application startup.

### Meeting minutes without paid APIs

Administrators and vice-secretaries can open **Meeting Minutes → Add Minutes** to type minutes manually or attach PDF, Word, text, spreadsheet, presentation, or image files. Minutes can be filtered by meeting date, downloaded, exported as PDF/DOCX/TXT, or shared through an authenticated link. AI recording and transcription remain optional and require an API key.

Protected routes use `@admin_required` and `@vs_required`; email verification is not required for account access.

---

## Deploy on Render

### Option A — Blueprint (recommended)

1. Push this repo to **GitHub** (or GitLab / Bitbucket).

2. Go to [https://dashboard.render.com](https://dashboard.render.com) → **New +** → **Blueprint**  
   *(or create services manually as below).*

### Option B — Manual setup

#### 1. PostgreSQL database

1. **New +** → **PostgreSQL**
2. Name: `net-platform-db`
3. Plan: Free (or Starter)
4. Create → copy the **Internal Database URL**

#### 2. Web service

1. **New +** → **Web Service**
2. Connect your repository
3. Settings:

| Setting | Value |
|---------|--------|
| **Name** | `net-platform` |
| **Runtime** | Python 3 |
| **Region** | Choose closest to users |
| **Branch** | `main` (or your default) |
| **Root Directory** | leave empty (or folder name if repo root differs) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --worker-class gthread --threads 8 -w 1 "app:create_app()" --bind 0.0.0.0:$PORT --timeout 120` |

> The `Procfile` already defines this start command if Render auto-detects it.
> This repository is the source of truth for the command (`Procfile` and this README); no `render.yaml` or `Dockerfile` is present. If Render has a dashboard-level Start Command override, set it to the same value.

#### 3. Environment variables

In the web service → **Environment**:

| Key | Value | Notes |
|-----|--------|--------|
| `SECRET_KEY` | long random string | required |
| `DATABASE_URL` | paste Internal Database URL from Postgres | required |
| `FLASK_ENV` | `production` | recommended |
| `OPENAI_API_KEY` | your key | optional |
| `GROQ_API_KEY` | your key | optional |
| `GOOGLE_VISION_API_KEY` | your key | optional, for image OCR |
| `ASSEMBLYAI_API_KEY` | your key | optional, for audio transcription |
| `MAIL_SERVER` | e.g. `smtp.gmail.com` | for real email |
| `MAIL_PORT` | `587` | |
| `MAIL_USE_TLS` | `true` | |
| `MAIL_USERNAME` | SMTP user | |
| `MAIL_PASSWORD` | SMTP password / app password | |
| `MAIL_DEFAULT_SENDER` | `NET Platform <you@domain.com>` | |

**Gmail tip:** use an [App Password](https://support.google.com/accounts/answer/185833), not your normal password.

#### 4. Deploy

Click **Create Web Service**. Render builds and starts the app.

On first boot:

- Tables are created
- Schema migrations run
- Default admin is seeded: `admin@net.org` / `Admin@1234`

Visit `https://<your-service>.onrender.com` and log in.

#### 5. Post-deploy checklist

- [ ] Log in as admin and change the default password  
- [ ] Create branches under **Admin → Branches**
- [ ] Test self-registration and immediate sign-in
- [ ] (Optional) Add custom domain under **Settings → Custom Domains**

---

## Render notes & troubleshooting

| Issue | Fix |
|-------|-----|
| App sleeps on free tier | First request after idle may take ~30–60s |
| WebSockets / chat | Use the gthread worker with Socket.IO threading mode (`--worker-class gthread --threads 8`) |
| `postgres://` URL | App auto-rewrites to `postgresql://` |
| Build fails on Pillow | Ensure build uses Python 3.11 (`runtime.txt`) |
| Emails not arriving | Check SMTP env vars; without them, links only appear in **Logs** |
| 500 on first load | Check **Logs** for DB connection errors; confirm `DATABASE_URL` |

View logs: Render dashboard → your service → **Logs**.

---

## Local development tips

```bash
# Run with debug (auto-reload)
python app.py

# Or via Flask CLI
export FLASK_APP=app:create_app
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=5000
```

- SQLite DB file: `instance/net_platform.db`
- Uploads: `uploads/`
- Without SMTP, verification links print in the terminal when someone registers

---

## Default credentials

| Role | Email | Password |
|------|--------|----------|
| Admin | `admin@net.org` | `Admin@1234` |

**Change immediately in production.**

---

## License

Internal use — Network Evangelistic Team.
#   L A I K I P I A - N E T W O R K - E V A G E L I S T I C - T E A M - W E B - A P P 
 
 