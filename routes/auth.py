"""
Authentication Routes
======================
Handles: login, logout, self-registration, email verification, change-password
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, bcrypt
from models.user import User
from models.branch import Branch
from services.email_service import send_verification_email, token_is_valid
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


# ── Login ────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if not current_user.email_verified:
            return redirect(url_for("auth.unverified"))
        return _role_redirect(current_user.role)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email, is_active=True).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            if not user.email_verified:
                login_user(user)  # temporary session so they can resend
                flash("Please verify your email before continuing.", "warning")
                return redirect(url_for("auth.unverified"))

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


# ── Register (public self-registration + admin can also use) ─────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated and current_user.role != "admin":
        return _role_redirect(current_user.role)

    is_admin = current_user.is_authenticated and current_user.role == "admin"
    branches = Branch.query.order_by(Branch.name).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "member")
        phone = request.form.get("phone", "").strip()
        residence = request.form.get("residence", "").strip()
        year = request.form.get("year", "").strip()
        branch_id = request.form.get("branch_id") or None

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("Email is already registered.")

        allowed_roles = {"member", "vice_secretary"}
        if is_admin:
            allowed_roles.add("admin")
        if role not in allowed_roles:
            role = "member"

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            # Admin-created accounts are auto-verified
            auto_verify = is_admin

            new_user = User(
                full_name=full_name,
                email=email,
                password_hash=bcrypt.generate_password_hash(password).decode(),
                role=role,
                phone=phone or None,
                residence=residence or None,
                year=year or None,
                branch_id=int(branch_id) if branch_id else None,
                is_active=True,
                email_verified=auto_verify,
            )
            db.session.add(new_user)
            db.session.commit()

            if is_admin:
                flash(f"Account created for {full_name} ({role}).", "success")
                return redirect(url_for("admin.members"))

            # Self-registration → send verification email
            sent = send_verification_email(new_user)
            if sent:
                flash(
                    "Account created! Check your email for a verification link.",
                    "success",
                )
            else:
                flash(
                    "Account created, but we could not send the verification email. "
                    "Please use Resend on the next page.",
                    "warning",
                )
            return redirect(url_for("auth.login"))

    return render_template(
        "auth/register.html",
        is_admin=is_admin,
        branches=branches,
    )


# ── Email verification ───────────────────────────────────────────────────────
@auth_bp.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Invalid or expired verification link.", "danger")
        return redirect(url_for("auth.login"))

    if user.email_verified:
        flash("Email already verified. You can sign in.", "info")
        return redirect(url_for("auth.login"))

    if not token_is_valid(user):
        flash("This verification link has expired. Please request a new one.", "warning")
        return redirect(url_for("auth.unverified"))

    user.email_verified = True
    user.verification_token = None
    user.verification_sent_at = None
    db.session.commit()
    flash("Email verified successfully! You can now sign in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/unverified", methods=["GET", "POST"])
def unverified():
    """Page shown when the user is logged in but email is not verified."""
    if current_user.is_authenticated and current_user.email_verified:
        return _role_redirect(current_user.role)

    if request.method == "POST":
        # Resend verification
        if current_user.is_authenticated:
            user = current_user
        else:
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email, is_active=True).first()
            if not user:
                flash("No account found with that email.", "danger")
                return render_template("auth/unverified.html")

        if user.email_verified:
            flash("This email is already verified. Please sign in.", "info")
            return redirect(url_for("auth.login"))

        # Rate-limit: don't resend more than once per 2 minutes
        if user.verification_sent_at and (
            datetime.utcnow() - user.verification_sent_at
        ).total_seconds() < 120:
            flash("Please wait a couple of minutes before requesting another email.", "warning")
        else:
            if send_verification_email(user):
                flash("Verification email sent. Check your inbox.", "success")
            else:
                flash("Could not send email. Contact an administrator.", "danger")

    return render_template("auth/unverified.html")


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    """Alias POST endpoint for resend forms."""
    return unverified()


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
