import os, json
from flask import Flask, redirect, url_for
from extensions import db, login_manager, bcrypt, socketio


def create_app():
    app = Flask(__name__)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        from config import ProductionConfig
        app.config.from_object(ProductionConfig)
    else:
        from config import DevelopmentConfig
        app.config.from_object(DevelopmentConfig)

    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)
    os.makedirs("instance", exist_ok=True)

    @app.template_filter('from_json')
    def from_json_filter(value):
        try:
            return json.loads(value) if value else []
        except Exception:
            return []

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    socketio.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.member import member_bp
    from routes.vice_secretary import vs_bp
    from routes.api import api_bp
    from routes.chat import chat_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(member_bp, url_prefix="/member")
    app.register_blueprint(vs_bp, url_prefix="/vs")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/chat")

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/sw.js")
    def service_worker():
        from flask import send_from_directory
        return send_from_directory("static", "sw.js",
                                   mimetype="application/javascript")

    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        from flask import send_from_directory
        from flask_login import current_user
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    from routes.chat_socket import register_socket_events
    register_socket_events(socketio)

    with app.app_context():
        db.create_all()
        _seed_admin()
        _seed_chat_rooms()
        _migrate_db(app)

    return app


def _seed_admin():
    from models.user import User
    from extensions import bcrypt
    if not User.query.filter_by(role="admin").first():
        admin = User(
            full_name="System Administrator",
            email="admin@net.org",
            password_hash=bcrypt.generate_password_hash("Admin@1234").decode(),
            role="admin",
            is_active=True,
        )
        db.session.add(admin)
        db.session.commit()
        print("✅  Default admin seeded  →  admin@net.org  /  Admin@1234")


def _seed_chat_rooms():
    from models.chat_message import ChatRoom
    rooms = [
        ("general", "🌍 General", "group"),
        ("prayer", "🙏 Prayer Requests", "group"),
        ("events", "📅 Events", "group"),
        ("announcements_room", "📢 Announcements", "group"),
    ]
    for room_id, name, rtype in rooms:
        if not ChatRoom.query.filter_by(room_id=room_id).first():
            db.session.add(ChatRoom(room_id=room_id, name=name, room_type=rtype))
    db.session.commit()


def _migrate_db(app):
    """
    Safely add new columns to existing tables.
    Works with both SQLite (local) and PostgreSQL (Railway).
    Uses information_schema to check if column exists before adding.
    """
    is_postgres = "postgresql" in app.config.get("SQLALCHEMY_DATABASE_URI", "")

    # Define migrations: (table, column, type)
    migrations = [
        ("chat_messages", "msg_type",    "VARCHAR(20) DEFAULT 'text'"),
        ("chat_messages", "file_url",    "VARCHAR(500)"),
        ("chat_messages", "file_name",   "VARCHAR(200)"),
        ("chat_messages", "file_size",   "INTEGER"),
        ("chat_messages", "reply_to_id", "INTEGER"),
        ("chat_messages", "is_deleted",  "BOOLEAN DEFAULT FALSE"),
        ("users",         "residence",   "VARCHAR(150)"),
        ("users",         "year",        "VARCHAR(50)"),
    ]

    with db.engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                if is_postgres:
                    # PostgreSQL: check information_schema first
                    check = conn.execute(db.text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=:t AND column_name=:c"
                    ), {"t": table, "c": column})
                    if check.fetchone() is None:
                        conn.execute(db.text(
                            f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                        ))
                        conn.commit()
                        print(f"✅ Migrated: {table}.{column}")
                else:
                    # SQLite: just try, ignore if exists
                    conn.execute(db.text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    ))
                    conn.commit()
            except Exception as e:
                # Column already exists — that's fine
                try:
                    conn.rollback()
                except Exception:
                    pass


if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True, host="0.0.0.0",
                 port=int(os.environ.get("PORT", 5000)),
                 allow_unsafe_werkzeug=True)
```

---

Also update `Procfile` — open it and replace with:
```
web: gunicorn --worker-class eventlet -w 1 app:create_app --bind 0.0.0.0:$PORT --timeout 120