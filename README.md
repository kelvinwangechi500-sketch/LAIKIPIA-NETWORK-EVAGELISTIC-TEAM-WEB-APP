# 🏛️ Network Evangelistic Team — Management Platform

A full-stack web application for managing Network Evangelistic Team operations.
Built with Python Flask · SQLite · OpenAI AI APIs · Offline-First Chat (IndexedDB)

---

## 📁 Project Structure

```
NET_Platform/
├── app.py                        ← Flask app factory & entry point
├── config.py                     ← All configuration settings
├── extensions.py                 ← Flask extensions (db, login, bcrypt)
├── requirements.txt              ← Python dependencies
├── .env.example                  ← Environment variable template
├── .gitignore
│
├── models/                       ← Database models (SQLAlchemy)
│   ├── __init__.py
│   ├── user.py                   ← User (admin/vice_secretary/member)
│   ├── attendance.py             ← Attendance records
│   ├── announcement.py           ← Announcements
│   ├── chat_message.py           ← Chat messages
│   ├── meeting_minutes.py        ← AI-generated minutes
│   └── branch.py                 ← Network branches/chapters
│
├── routes/                       ← URL route handlers (Blueprints)
│   ├── __init__.py
│   ├── auth.py                   ← Login / logout / register / change-password
│   ├── admin.py                  ← Admin dashboard, members, announcements
│   ├── member.py                 ← Member dashboard, profile, attendance
│   ├── vice_secretary.py         ← OCR upload, manual attendance, recording
│   └── api.py                    ← REST API (chat sync, attendance AJAX)
│
├── services/                     ← AI / external service integrations
│   ├── __init__.py
│   ├── ocr_service.py            ← OpenAI Vision → extract names from photo
│   └── ai_service.py             ← Whisper transcription + GPT-4o summarize
│
├── static/
│   ├── css/main.css              ← Full stylesheet (red/white/grey theme)
│   ├── js/main.js                ← Frontend helpers
│   └── img/logo.png              ← NET organization logo
│
├── templates/
│   ├── shared/sidebar.html       ← Reusable sidebar macro (with logo)
│   ├── auth/
│   │   ├── login.html            ← Login page
│   │   └── register.html        ← Create member (admin only)
│   ├── admin/
│   │   ├── dashboard.html        ← Admin overview
│   │   ├── members.html          ← Member management
│   │   ├── announcements.html    ← Post/delete announcements
│   │   ├── attendance.html       ← Attendance analytics
│   │   ├── minutes.html          ← Meeting minutes archive
│   │   └── branches.html         ← Network branches
│   ├── member/
│   │   ├── dashboard.html        ← Member overview + announcements
│   │   ├── attendance.html       ← Personal attendance history
│   │   ├── chat.html             ← Offline-first chat (IndexedDB)
│   │   └── profile.html          ← Profile + change password
│   └── vice_secretary/
│       ├── dashboard.html        ← VS overview
│       ├── upload_attendance.html  ← OCR photo upload
│       ├── confirm_attendance.html ← Review AI matches before saving
│       ├── manual_attendance.html  ← Checkbox attendance form
│       └── record_meeting.html     ← Voice recording + AI transcription
│
├── instance/                     ← Auto-created: contains net_platform.db
└── uploads/                      ← Auto-created: user-uploaded files
```

---

## 🚀 Setup Guide (VSCode)

### Step 1 — Prerequisites

Make sure you have installed:
- **Python 3.10+** → https://python.org/downloads
- **VSCode** → https://code.visualstudio.com
- **Python extension for VSCode** (ms-python.python)

### Step 2 — Open Project in VSCode

```bash
# In your terminal (or VSCode integrated terminal):
cd path/to/NET_Platform
code .
```

### Step 3 — Create a Virtual Environment

Open the **VSCode integrated terminal** (`Ctrl + backtick`) and run:

```bash
# Create virtual environment
python -m venv venv

# Activate it:
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

You should now see `(venv)` at the start of your terminal prompt.

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs Flask, SQLAlchemy, Flask-Login, Flask-Bcrypt, OpenAI, and all other packages.

### Step 5 — Set Up Environment Variables

```bash
# Copy the example file
cp .env.example .env
```

Open `.env` in VSCode and fill in your values:

```env
SECRET_KEY=make-this-a-long-random-string-abc123xyz

# Get your OpenAI key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-actual-openai-key-here
```

> ⚠️ **Important:** Without `OPENAI_API_KEY`, the app runs fine but OCR and
> AI transcription features will be disabled (they return empty results gracefully).

### Step 6 — Run the Application

```bash
python app.py
```

You should see:
```
✅  Default admin seeded  →  admin@net.org  /  Admin@1234
 * Running on http://0.0.0.0:5000
```

### Step 7 — Open in Browser

Navigate to: **http://localhost:5000**

---

## 🔑 Default Login Credentials

| Role           | Email              | Password    |
|----------------|--------------------|-------------|
| Admin          | admin@net.org      | Admin@1234  |

> ⚠️ **Change the admin password immediately** after first login via the Profile page.

---

## 👥 User Roles & Access

### 🔴 Admin
- Full platform access
- Create/delete/deactivate member accounts
- Post and manage announcements
- View all attendance records and analytics
- View meeting minutes archive
- Manage network branches

### 🟡 Vice Secretary
- Upload photo of attendance sheet → AI extracts and matches names
- Manual attendance recording
- Record meeting audio → AI transcribes and generates minutes
- View attendance records

### 🟢 Member
- View announcements board
- View personal attendance history and rate
- Chat with team members (offline-capable)
- Update personal profile and password

---

## 🤖 AI Features Setup

### OCR Attendance (OpenAI Vision)

1. Vice Secretary logs in → Upload Attendance
2. Select meeting date
3. Take/upload a photo of the paper attendance sheet
4. The app sends the image to **GPT-4o Vision**
5. Names are extracted and fuzzy-matched to the member database
6. VS reviews matches and saves

**Requires:** `OPENAI_API_KEY` with access to `gpt-4o`

### Meeting Voice Recording (Whisper + GPT-4o)

1. Vice Secretary → Record Meeting
2. Click the 🔴 record button (browser mic access required)
3. Speak/record the meeting
4. Click stop, then "Transcribe & Generate Minutes"
5. **OpenAI Whisper** converts audio → text
6. **GPT-4o** generates a summary and action points
7. Minutes are saved automatically to the database

**Requires:** `OPENAI_API_KEY` with access to `whisper-1` and `gpt-4o`

---

## 💬 Offline Chat Architecture

The chat system is designed for **low-connectivity environments**:

1. **Online:** Messages are sent directly to the Flask `/api/chat/send` endpoint
2. **Offline:** Messages are stored in the browser's **IndexedDB** (local storage that survives page refresh)
3. **Reconnect:** When internet is restored, the app automatically syncs all pending messages to the server via `/api/chat/sync`
4. **Deduplication:** Each message has a unique `client_id` (UUID) to prevent duplicates during sync

No Service Worker is required for this basic implementation. The logic is entirely in `chat.html`.

---

## 🛠️ VSCode Recommended Extensions

Install these from the VSCode Extensions panel (`Ctrl+Shift+X`):

| Extension | Purpose |
|-----------|---------|
| `ms-python.python` | Python language support |
| `ms-python.flake8` | Python linting |
| `batisteo.vscode-django` | Jinja2/HTML template syntax |
| `bradlc.vscode-tailwindcss` | CSS IntelliSense |
| `ms-python.debugpy` | Flask debugging |

### VSCode launch.json (for debugging)

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Flask",
      "type": "debugpy",
      "request": "launch",
      "module": "flask",
      "env": {
        "FLASK_APP": "app.py",
        "FLASK_DEBUG": "1"
      },
      "args": ["run", "--no-debugger", "--no-reload"],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

Then press **F5** to start the app with full debugging support.

---

## 🗄️ Database Schema

The SQLite database is auto-created at `instance/net_platform.db`.

```
users               → id, full_name, email, password_hash, role,
                      phone, branch_id, is_active, joined_date, last_seen

attendance          → id, user_id, meeting_date, status, source,
                      notes, recorded_by, created_at
                      UNIQUE(user_id, meeting_date)

announcements       → id, title, body, author_id, is_pinned,
                      audience, created_at

chat_messages       → id, room, sender_id, body, client_id, created_at

meeting_minutes     → id, meeting_date, title, transcript, summary,
                      action_points (JSON), audio_file, recorded_by

branches            → id, name, location, leader_name, created_at
```

---

## 🔒 Security Notes

- Passwords are hashed with **bcrypt** (never stored in plain text)
- Session tokens expire after **8 hours** of inactivity
- All dashboard routes require login (`@login_required`)
- Admin/VS routes have additional role checks (`@admin_required`, `@vs_required`)
- File uploads are validated by extension before saving
- `.env` file is excluded from git via `.gitignore`

---

## 🚢 Deployment (Production)

### Option A — Simple VPS (DigitalOcean, Linode, etc.)

```bash
# Install gunicorn (already in requirements.txt)
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

Use **Nginx** as a reverse proxy in front of gunicorn.

### Option B — Railway / Render (free tier)

1. Push to GitHub
2. Connect repo to Railway or Render
3. Set environment variables in the platform dashboard
4. Set start command: `gunicorn "app:create_app()"`

### Option C — Switch to PostgreSQL (production DB)

In `.env`:
```env
DATABASE_URL=postgresql://user:password@host:5432/net_platform
```

Install: `pip install psycopg2-binary`

---

## 📞 API Endpoints Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | None | Login |
| GET | `/auth/logout` | Any | Logout |
| POST | `/auth/register` | Admin | Create user |
| GET | `/api/chat/messages?room=general` | Any | Fetch messages |
| POST | `/api/chat/send` | Any | Send message |
| POST | `/api/chat/sync` | Any | Bulk sync offline messages |
| GET | `/api/announcements` | Any | List announcements |
| GET | `/api/attendance/by-date?date=YYYY-MM-DD` | Any | Attendance by date |
| GET | `/api/attendance/member/<id>` | Self/Admin | Member attendance |
| POST | `/vs/attendance/upload` | VS/Admin | OCR photo upload |
| POST | `/vs/meeting/transcribe` | VS/Admin | Audio → AI minutes |

---

## 🆘 Troubleshooting

**"Module not found" error:**
→ Make sure your virtual environment is activated (`source venv/bin/activate`)

**Database errors on first run:**
→ Delete `instance/net_platform.db` and restart — it will recreate

**OCR returns empty list:**
→ Check that `OPENAI_API_KEY` is set correctly in `.env`
→ Ensure the image is clear and names are legible

**Microphone not working in recording:**
→ Chrome/Edge required for `getUserMedia`. Must be on HTTPS in production.
→ Localhost works without HTTPS for development.

**Chat messages not syncing:**
→ Check browser console for errors
→ Ensure you are logged in when the sync attempt happens

---

*Network Evangelistic Team Management Platform — Built with Flask & Love ✝️*
