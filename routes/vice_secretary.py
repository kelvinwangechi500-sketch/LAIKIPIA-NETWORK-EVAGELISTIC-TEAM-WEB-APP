"""Vice Secretary Routes - Attendance, OCR, Meeting Recording"""
import os, json, uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, Response
from flask_login import login_required, current_user
from utils.decorators import vs_required
from extensions import db, bcrypt
from models.user import User
from models.attendance import Attendance
from models.meeting_minutes import MeetingMinutes
from datetime import datetime, date

vs_bp = Blueprint("vs", __name__)


def allowed_image(filename):
    exts = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    return "." in filename and filename.rsplit(".",1)[1].lower() in exts

def allowed_audio(filename):
    exts = current_app.config["ALLOWED_AUDIO_EXTENSIONS"]
    return "." in filename and filename.rsplit(".",1)[1].lower() in exts

def _log(action, details=""):
    from services.audit_service import log_action
    log_action(current_user.id, action, details)

# ── Dashboard ─────────────────────────────────────────────────────────────────
@vs_bp.route("/dashboard")
@login_required
@vs_required
def dashboard():
    date_filter = request.args.get("date", "")
    selected_date = None
    filtered_records = []

    all_dates = (
        db.session.query(Attendance.meeting_date)
        .distinct()
        .order_by(Attendance.meeting_date.desc())
        .all()
    )
    all_dates = [d[0] for d in all_dates]

    if date_filter:
        try:
            selected_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            filtered_records = (
                Attendance.query
                .join(User, Attendance.user_id == User.id)
                .filter(Attendance.meeting_date == selected_date)
                .order_by(User.full_name)
                .all()
            )
        except Exception:
            pass
    elif all_dates:
        selected_date = all_dates[0]
        date_filter = str(selected_date)
        filtered_records = (
            Attendance.query
            .join(User, Attendance.user_id == User.id)
            .filter(Attendance.meeting_date == selected_date)
            .order_by(User.full_name)
            .all()
        )

    present_count = sum(1 for r in filtered_records if r.status == "present")
    absent_count = sum(1 for r in filtered_records if r.status == "absent")
    total_count = len(filtered_records)
    recent_minutes = MeetingMinutes.query.order_by(MeetingMinutes.meeting_date.desc()).limit(5).all()
    total_meetings = len(all_dates)

    return render_template(
        "vice_secretary/dashboard.html",
        filtered_records=filtered_records,
        all_dates=all_dates,
        selected_date=selected_date,
        date_filter=date_filter,
        present_count=present_count,
        absent_count=absent_count,
        total_count=total_count,
        total_meetings=total_meetings,
        recent_minutes=recent_minutes,
    )

# ── OCR Upload ────────────────────────────────────────────────────────────────
@vs_bp.route("/attendance/upload", methods=["GET","POST"])
@login_required
@vs_required
def upload_attendance():
    if request.method == "POST":
        meeting_date_str = request.form.get("meeting_date")
        file = request.files.get("attendance_image")
        if not file or not allowed_image(file.filename):
            flash("Please upload a valid image (PNG/JPG).", "warning")
            return redirect(url_for("vs.upload_attendance"))
        meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
        ext = file.filename.rsplit(".",1)[1].lower()
        fname = f"attendance_{meeting_date}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
        file.save(save_path)
        from services.ocr_service import extract_attendance_from_image
        ocr_rows = extract_attendance_from_image(save_path)
        all_members = User.query.filter_by(is_active=True).all()
        from services.attendance_service import fuzzy_match_members
        matched, unmatched = fuzzy_match_members(ocr_rows, all_members)
        _log("OCR_UPLOAD", f"Uploaded attendance for {meeting_date}, extracted {len(ocr_rows)} rows")
        return render_template("vice_secretary/confirm_attendance.html",
            meeting_date=meeting_date, matched=matched, unmatched=unmatched,
            all_members=all_members, image_file=fname)
    return render_template("vice_secretary/upload_attendance.html", today=str(date.today()))

@vs_bp.route("/attendance/save", methods=["POST"])
@login_required
@vs_required
def save_attendance():
    meeting_date_str = request.form.get("meeting_date")
    meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    present_ids = request.form.getlist("present_ids")

    # Handle new members from unmatched
    new_names = request.form.getlist("new_name[]")
    new_residences = request.form.getlist("new_residence[]")
    new_years = request.form.getlist("new_year[]")
    new_presents = request.form.getlist("new_present[]")

    new_member_ids = []
    for i, name in enumerate(new_names):
        name = name.strip()
        if not name:
            continue
        from services.attendance_service import generate_placeholder_email
        email = generate_placeholder_email()
        new_user = User(
            full_name=name,
            email=email,
            password_hash=bcrypt.generate_password_hash(uuid.uuid4().hex).decode(),
            role="member",
            residence=new_residences[i] if i < len(new_residences) else "",
            year=new_years[i] if i < len(new_years) else "",
            is_active=True,
        )
        db.session.add(new_user)
        db.session.flush()
        if str(i) in new_presents or name in new_presents:
            new_member_ids.append(new_user.id)
        _log("AUTO_CREATE_MEMBER", f"Auto-created member: {name} ({email})")

    all_members = User.query.filter_by(is_active=True).all()
    saved = 0
    for member in all_members:
        status = "present" if str(member.id) in present_ids or member.id in new_member_ids else "absent"
        existing = Attendance.query.filter_by(user_id=member.id, meeting_date=meeting_date).first()
        if existing:
            existing.status = status
        else:
            db.session.add(Attendance(user_id=member.id, meeting_date=meeting_date,
                status=status, source="ocr_upload", recorded_by=current_user.id))
        saved += 1

    db.session.commit()
    _log("SAVE_ATTENDANCE", f"Saved attendance for {meeting_date}: {len(present_ids)} present")
    flash(f"Attendance for {meeting_date} saved — {len(present_ids)} present.", "success")
    return redirect(url_for("vs.dashboard"))

# ── Manual Attendance ─────────────────────────────────────────────────────────
@vs_bp.route("/attendance/manual", methods=["GET","POST"])
@login_required
@vs_required
def manual_attendance():
    members = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    if request.method == "POST":
        meeting_date_str = request.form.get("meeting_date")
        meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
        present_ids = request.form.getlist("present_ids")
        for member in members:
            status = "present" if str(member.id) in present_ids else "absent"
            existing = Attendance.query.filter_by(user_id=member.id, meeting_date=meeting_date).first()
            if existing:
                existing.status = status
            else:
                db.session.add(Attendance(user_id=member.id, meeting_date=meeting_date,
                    status=status, source="manual", recorded_by=current_user.id))
        db.session.commit()
        _log("MANUAL_ATTENDANCE", f"Manual attendance for {meeting_date}")
        flash("Attendance recorded.", "success")
        return redirect(url_for("vs.dashboard"))
    return render_template("vice_secretary/manual_attendance.html", members=members, today=str(date.today()))

# ── Meeting Minutes (VS View + Edit) ─────────────────────────────────────────
@vs_bp.route("/minutes")
@login_required
@vs_required
def minutes():
    all_minutes = MeetingMinutes.query.order_by(MeetingMinutes.meeting_date.desc()).all()
    return render_template("vice_secretary/minutes.html", minutes=all_minutes)

@vs_bp.route("/minutes/<int:mid>/edit", methods=["GET","POST"])
@login_required
@vs_required
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
        _log("EDIT_MINUTES", f"VS edited minutes id={mid}")
        flash("Minutes updated.", "success")
        return redirect(url_for("vs.minutes"))
    return render_template("vice_secretary/edit_minutes.html", minutes=m)

@vs_bp.route("/minutes/<int:mid>/export/<fmt>")
@login_required
@vs_required
def export_minutes(mid, fmt):
    from routes.admin import export_minutes as admin_export
    return admin_export(mid, fmt)

# ── Attendance Export ─────────────────────────────────────────────────────────
@vs_bp.route("/attendance/export/<fmt>")
@login_required
@vs_required
def export_attendance(fmt):
    date_filter = request.args.get("date","")
    q = Attendance.query
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
            headers={"Content-Disposition":"attachment; filename=attendance.csv"})
    elif fmt == "excel":
        from services.export_service import export_attendance_excel
        data = export_attendance_excel(records)
        return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition":"attachment; filename=attendance.xlsx"})
    flash("Invalid format.", "warning")
    return redirect(url_for("vs.dashboard"))

# ── Meeting Recording ─────────────────────────────────────────────────────────
@vs_bp.route("/meeting/record", methods=["GET"])
@login_required
@vs_required
def record_meeting():
    return render_template("vice_secretary/record_meeting.html", today=str(date.today()))

@vs_bp.route("/meeting/transcribe", methods=["POST"])
@login_required
@vs_required
def transcribe_meeting():
    audio_file = request.files.get("audio")
    meeting_date_str = request.form.get("meeting_date", str(date.today()))
    title = request.form.get("title","Meeting Minutes")
    if not audio_file:
        return jsonify({"error":"No audio file"}), 400
    fname = f"meeting_{meeting_date_str}_{uuid.uuid4().hex[:8]}.webm"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
    audio_file.save(save_path)
    from services.ai_service import transcribe_audio, summarize_transcript
    transcript = transcribe_audio(save_path)
    summary, action_points = summarize_transcript(transcript)
    meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    m = MeetingMinutes(meeting_date=meeting_date, title=title,
        transcript=transcript, summary=summary,
        action_points=json.dumps(action_points), audio_file=fname,
        recorded_by=current_user.id)
    db.session.add(m)
    db.session.commit()
    _log("RECORD_MEETING", f"Transcribed meeting: {title} on {meeting_date}")
    return jsonify({"success":True, "minutes_id":m.id,
        "transcript":transcript, "summary":summary, "action_points":action_points})