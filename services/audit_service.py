"""Audit logging service"""
from extensions import db
from models.audit_log import AuditLog
from flask import request

def log_action(user_id, action: str, details: str = ""):
    try:
        ip = request.remote_addr if request else "unknown"
        log = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip)
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
