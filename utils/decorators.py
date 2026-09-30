"""
Role-Based Access Control (RBAC) decorators
============================================
Usage:
    @login_required
    @role_required("admin")
    def admin_only(): ...

    @login_required
    @role_required("admin", "vice_secretary")
    def staff_only(): ...

    @login_required
    @verified_required
    def needs_verified_email(): ...
"""

from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user


def role_required(*roles):
    """Allow access only if current_user.role is in the given roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("auth.login"))
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    """Shortcut: admin only."""
    return role_required("admin")(f)


def vs_required(f):
    """Shortcut: admin or vice_secretary."""
    return role_required("admin", "vice_secretary")(f)


def verified_required(f):
    """Require that the user's email has been verified."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "email_verified", True):
            flash("Please verify your email address to continue.", "warning")
            return redirect(url_for("auth.unverified"))
        return f(*args, **kwargs)
    return decorated
