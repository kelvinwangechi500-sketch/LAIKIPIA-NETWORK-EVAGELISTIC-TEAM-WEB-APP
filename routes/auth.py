"""
Authentication Routes
======================
Handles: login, logout, register (admin-only), change-password
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, bcrypt
from models.user import User
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


# ── Login ────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _role_redirect(current_user.role)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email, is_active=True).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            session.permanent = True
            flash(f"Welcome back, {user.full_name.split()[0]}!", "success")
            return _role_redirect(user.role)

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


# ── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ── Register (admin creates accounts) ────────────────────────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.role != "admin":
        flash("Unauthorized.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "member")
        phone = request.form.get("phone", "").strip()

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
        else:
            new_user = User(
                full_name=full_name,
                email=email,
                password_hash=bcrypt.generate_password_hash(password).decode(),
                role=role,
                phone=phone,
                is_active=True,
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f"Account created for {full_name}.", "success")
            return redirect(url_for("admin.members"))

    return render_template("auth/register.html")


# ── Change Password ───────────────────────────────────────────────────────────
@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    old_pw = request.form.get("old_password", "")
    new_pw = request.form.get("new_password", "")

    if bcrypt.check_password_hash(current_user.password_hash, old_pw):
        current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode()
        db.session.commit()
        flash("Password updated successfully.", "success")
    else:
        flash("Current password incorrect.", "danger")

    return redirect(url_for("member.profile"))


# ── Helper ────────────────────────────────────────────────────────────────────
def _role_redirect(role):
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    elif role == "vice_secretary":
        return redirect(url_for("vs.dashboard"))
    return redirect(url_for("member.dashboard"))
