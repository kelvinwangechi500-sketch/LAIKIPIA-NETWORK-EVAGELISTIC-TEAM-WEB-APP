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
        _migrate_db()

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

def _migrate_db():
    """Add new columns to existing tables without losing data."""
    migrations = [
        "ALTER TABLE chat_messages ADD COLUMN msg_type VARCHAR(20) DEFAULT 'text'",
        "ALTER TABLE chat_messages ADD COLUMN file_url VARCHAR(500)",
        "ALTER TABLE chat_messages ADD COLUMN file_name VARCHAR(200)",
        "ALTER TABLE chat_messages ADD COLUMN file_size INTEGER",
        "ALTER TABLE chat_messages ADD COLUMN reply_to_id INTEGER",
        "ALTER TABLE chat_messages ADD COLUMN is_deleted BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN residence VARCHAR(150)",
        "ALTER TABLE users ADD COLUMN year VARCHAR(50)",
    ]
    from extensions import db
    for sql in migrations:
        try:
            db.session.execute(db.text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()
            
if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True, host="0.0.0.0",
                 port=int(os.environ.get("PORT", 5000)),
                 allow_unsafe_werkzeug=True)