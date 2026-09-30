"""Admin Routes — Full system control"""
import json, io
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, Response, send_file
from flask_login import login_required, current_user
from extensions import db, bcrypt
from utils.decorators import admin_required
from models.user import User
from models.announcement import Announcement
from models.attendance import Attendance
from models.meeting_minutes import MeetingMinutes
from models.branch import Branch
from models.audit_log import AuditLog
from datetime import datetime, date

admin_bp = Blueprint("admin", __name__)


def _log(action, details=""):
    from services.audit_service import log_action
    log_action(current_user.id, action, details)

# ── Dashboard ─────────────────────────────────────────────────────────────────
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    total_members = User.query.filter_by(is_active=True).count()
    total_announcements = Announcement.query.count()
    total_meetings = MeetingMinutes.query.count()
    recent_announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
    recent_members = User.query.order_by(User.joined_date.desc()).limit(5).all()
    recent_minutes = MeetingMinutes.query.order_by(MeetingMinutes.meeting_date.desc()).limit(3).all()
    total_attendance = Attendance.query.count()
    present_count = Attendance.query.filter_by(status="present").count()
    att_rate = round((present_count/total_attendance*100) if total_attendance else 0, 1)
    return render_template("admin/dashboard.html",
        total_members=total_members, total_announcements=total_announcements,
        total_meetings=total_meetings, recent_announcements=recent_announcements,
        recent_members=recent_members, recent_minutes=recent_minutes,
        att_rate=att_rate, total_attendance=total_attendance)

# ── Members ───────────────────────────────────────────────────────────────────
@admin_bp.route("/members")
@login_required
@admin_required
def members():
    all_members = User.query.order_by(User.full_name).all()
    branches = Branch.query.all()
    return render_template("admin/members.html", members=all_members, branches=branches)

@admin_bp.route("/members/<int:uid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_member(uid):
    user = User.query.get_or_404(uid)
    if user.role == "admin":
        flash("Cannot delete an admin account.", "danger")
        return redirect(url_for("admin.members"))
    name = user.full_name
    email = user.email
    # Delete related records first to avoid foreign key errors
    Attendance.query.filter_by(user_id=uid).delete()
    from models.chat_message import ChatMessage, MessageRead
    MessageRead.query.filter(
        MessageRead.message_id.in_(
            db.session.query(ChatMessage.id).filter_by(sender_id=uid)
        )
    ).delete(synchronize_session=False)
    ChatMessage.query.filter_by(sender_id=uid).delete()
    db.session.delete(user)
    db.session.commit()
    _log("DELETE_MEMBER", f"Permanently deleted member: {email} ({name})")
    flash(f"{name} has been permanently deleted.", "success")
    return redirect(url_for("admin.members"))

@admin_bp.route("/members/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_member(uid):
    user = User.query.get_or_404(uid)
    branches = Branch.query.all()
    if request.method == "POST":
        user.full_name = request.form.get("full_name", user.full_name).strip()
        user.email = request.form.get("email", user.email).strip().lower()
        user.phone = request.form.get("phone", "").strip()
        user.residence = request.form.get("residence", "").strip()
        user.year = request.form.get("year", "").strip()
        user.role = request.form.get("role", user.role)
        user.branch_id = request.form.get("branch_id") or None
        new_pw = request.form.get("new_password", "").strip()
        if new_pw:
            user.password_hash = bcrypt.generate_password_hash(new_pw).decode()
            _log("RESET_PASSWORD", f"Reset password for {user.email}")
        db.session.commit()
        _log("EDIT_MEMBER", f"Edited member {user.email}")
        flash(f"{user.full_name} updated.", "success")
        return redirect(url_for("admin.members"))
    return render_template("admin/edit_member.html", user=user, branches=branches)

@admin_bp.route("/members/<int:uid>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_member(uid):
    user = User.query.get_or_404(uid)
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    _log("TOGGLE_MEMBER", f"{user.email} {status}")
    flash(f"{user.full_name} has been {status}.", "success")
    return redirect(url_for("admin.members"))

# ── Announcements ─────────────────────────────────────────────────────────────
@admin_bp.route("/announcements")
@login_required
@admin_required
def announcements():
    items = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("admin/announcements.html", announcements=items)

@admin_bp.route("/announcements/new", methods=["POST"])
@login_required
@admin_required
def new_announcement():
    ann = Announcement(
        title=request.form.get("title","").strip(),
        body=request.form.get("body","").strip(),
        author_id=current_user.id,
        is_pinned=request.form.get("is_pinned")=="on",
        audience=request.form.get("audience","all"),
    )
    db.session.add(ann)
    db.session.commit()
    _log("POST_ANNOUNCEMENT", ann.title)
    flash("Announcement posted.", "success")
    return redirect(url_for("admin.announcements"))

@admin_bp.route("/announcements/<int:aid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    db.session.delete(ann)
    db.session.commit()
    flash("Announcement deleted.", "info")
    return redirect(url_for("admin.announcements"))

# ── Attendance ────────────────────────────────────────────────────────────────
@admin_bp.route("/attendance")
@login_required
@admin_required
def attendance():
    date_filter = request.args.get("date", "")
    dates = db.session.query(Attendance.meeting_date).distinct().order_by(
        Attendance.meeting_date.desc()
    ).all()
    dates = [d[0] for d in dates]
    if not date_filter and dates:
        date_filter = str(dates[0])
    q = Attendance.query.join(User, Attendance.user_id == User.id)
    if date_filter:
        try:
            fd = datetime.strptime(date_filter, "%Y-%m-%d").date()
            q = q.filter(Attendance.meeting_date == fd)
        except Exception:
            pass
    records = q.order_by(User.full_name).all()
    return render_template("admin/attendance.html",
        records=records, dates=dates, date_filter=date_filter)

@admin_bp.route("/attendance/<int:rid>/edit", methods=["POST"])
@login_required
@admin_required
def edit_attendance(rid):
    rec = Attendance.query.get_or_404(rid)
    rec.status = request.form.get("status", rec.status)
    rec.notes = request.form.get("notes","")
    db.session.commit()
    _log("EDIT_ATTENDANCE", f"Edited attendance id={rid}")
    flash("Attendance updated.", "success")
    return redirect(url_for("admin.attendance"))

@admin_bp.route("/attendance/<int:rid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_attendance(rid):
    rec = Attendance.query.get_or_404(rid)
    db.session.delete(rec)
    db.session.commit()
    flash("Record deleted.", "info")
    return redirect(url_for("admin.attendance"))

@admin_bp.route("/attendance/export/<fmt>")
@login_required
@admin_required
def export_attendance(fmt):
    date_filter = request.args.get("date","")
    q = Attendance.query.join(User, Attendance.user_id == User.id)
    if date_filter:
        try:
            fd = datetime.strptime(date_filter, "%Y-%m-%d").date()
            q = q.filter(Attendance.meeting_date == fd)
        except:
            pass
    records = q.order_by(Attendance.meeting_date.desc()).all()
    if fmt == "csv":
        from services.attendance_service import export_attendance_csv
        data = export_attendance_csv(records)
        return Response(data, mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=attendance.csv"})
    elif fmt == "excel":
        from services.export_service import export_attendance_excel
        data = export_attendance_excel(records)
        return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=attendance.xlsx"})
    elif fmt == "pdf":
        from services.export_service import _attendance_pdf
        data = _attendance_pdf(records)
        return Response(data, mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=attendance.pdf"})
    flash("Invalid format.", "warning")
    return redirect(url_for("admin.attendance"))

# ── Meeting Minutes ───────────────────────────────────────────────────────────
@admin_bp.route("/minutes")
@login_required
@admin_required
def minutes():
    all_minutes = MeetingMinutes.query.order_by(MeetingMinutes.meeting_date.desc()).all()
    return render_template("admin/minutes.html", minutes=all_minutes)

@admin_bp.route("/minutes/<int:mid>/edit", methods=["GET","POST"])
@login_required
@admin_required
def edit_minutes(mid):
    m = MeetingMinutes.query.get_or_404(mid)
    if request.method == "POST":
        m.title = request.form.get("title", m.title).strip()
        m.summary = request.form.get("summary","").strip()
        m.transcript = request.form.get("transcript","").strip()
        ap_raw = request.form.get("action_points","").strip()
        try:
            json.loads(ap_raw)
            m.action_points = ap_raw
        except:
            pts = [x.strip() for x in ap_raw.split("\n") if x.strip()]
            m.action_points = json.dumps(pts)
        db.session.commit()
        _log("EDIT_MINUTES", f"Edited minutes id={mid}")
        flash("Meeting minutes updated.", "success")
        return redirect(url_for("admin.minutes"))
    return render_template("admin/edit_minutes.html", minutes=m)

@admin_bp.route("/minutes/<int:mid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_minutes(mid):
    m = MeetingMinutes.query.get_or_404(mid)
    db.session.delete(m)
    db.session.commit()
    flash("Minutes deleted.", "info")
    return redirect(url_for("admin.minutes"))

@admin_bp.route("/minutes/<int:mid>/export/<fmt>")
@login_required
@admin_required
def export_minutes(mid, fmt):
    m = MeetingMinutes.query.get_or_404(mid)
    if fmt == "pdf":
        from services.export_service import export_minutes_pdf
        data = export_minutes_pdf(m)
        return Response(data, mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=minutes_{m.meeting_date}.pdf"})
    elif fmt == "docx":
        from services.export_service import export_minutes_docx
        data = export_minutes_docx(m)
        return Response(data, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=minutes_{m.meeting_date}.docx"})
    elif fmt == "txt":
        pts = []
        try: pts = json.loads(m.action_points or "[]")
        except: pts = [m.action_points or ""]
        txt = f"MEETING MINUTES\n{'='*40}\nTitle: {m.title}\nDate: {m.meeting_date}\n\nSUMMARY\n{m.summary or ''}\n\nACTION POINTS\n" + "\n".join(f"- {p}" for p in pts) + f"\n\nTRANSCRIPT\n{m.transcript or ''}"
        return Response(txt, mimetype="text/plain",
            headers={"Content-Disposition": f"attachment; filename=minutes_{m.meeting_date}.txt"})
    flash("Invalid format.", "warning")
    return redirect(url_for("admin.minutes"))


@admin_bp.route("/members/<int:uid>/verify", methods=["POST"])
@login_required
@admin_required
def verify_member(uid):
    user = User.query.get_or_404(uid)
    user.email_verified = True
    user.verification_token = None
    user.verification_sent_at = None
    db.session.commit()
    _log("VERIFY_EMAIL", f"Manually verified email for {user.email}")
    flash(f"{user.full_name}'s email has been marked as verified.", "success")
    return redirect(url_for("admin.members"))

# ── Branches ──────────────────────────────────────────────────────────────────
@admin_bp.route("/branches", methods=["GET","POST"])
@login_required
@admin_required
def branches():
    if request.method == "POST":
        b = Branch(name=request.form.get("name","").strip(),
                   location=request.form.get("location","").strip(),
                   leader_name=request.form.get("leader_name","").strip())
        db.session.add(b)
        db.session.commit()
        flash("Branch created.", "success")
        return redirect(url_for("admin.branches"))
    return render_template("admin/branches.html", branches=Branch.query.all())

# ── Audit Logs ────────────────────────────────────────────────────────────────
@admin_bp.route("/audit-logs")
@login_required
@admin_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_logs.html", logs=logs)