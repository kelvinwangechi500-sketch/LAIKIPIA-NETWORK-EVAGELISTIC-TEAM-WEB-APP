"""
Vice Secretary Routes
======================
Attendance photo upload + OCR + AI matching + auto-record new members.
Meeting voice recording + AI transcription.
"""

import os
import json
import uuid
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, jsonify
)
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from models.user import User
from models.attendance import Attendance
from models.meeting_minutes import MeetingMinutes
from datetime import datetime, date

vs_bp = Blueprint("vs", __name__)

# ── Role Check ────────────────────────────────────────────────────────────────
def vs_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ("admin", "vice_secretary"):
            flash("Access restricted.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

# ── File Validators ───────────────────────────────────────────────────────────
def allowed_image(filename):
    exts = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts

def allowed_audio(filename):
    exts = current_app.config["ALLOWED_AUDIO_EXTENSIONS"]
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts

# ── Dashboard ───────────────────────────────────────────────────────────────
@vs_bp.route("/dashboard")
@login_required
@vs_required
def dashboard():
    recent_records = (
        Attendance.query
        .join(User, Attendance.user_id == User.id)
        .order_by(Attendance.meeting_date.desc())
        .limit(50)
        .all()
    )
    return render_template("vice_secretary/dashboard.html", recent_records=recent_records)

# ── OCR Attendance Upload ─────────────────────────────────────────────────────
@vs_bp.route("/attendance/upload", methods=["GET", "POST"])
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

        # Save uploaded image
        ext = file.filename.rsplit(".", 1)[1].lower()
        fname = f"attendance_{meeting_date}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
        file.save(save_path)

        # Extract names and structured data from OCR service
        from services.ocr_service import extract_names_from_image
        ocr_results = extract_names_from_image(save_path)

        # Names list for fuzzy matching
        extracted_names = [m['name'] for m in ocr_results if m.get('name')]
        ocr_data_map = {m['name'].lower(): m for m in ocr_results}  # For auto-adding new members

        # Match against existing members
        all_members = User.query.filter_by(is_active=True).all()
        matched, unmatched = _fuzzy_match(extracted_names, all_members)

        return render_template(
            "vice_secretary/confirm_attendance.html",
            meeting_date=meeting_date,
            matched=matched,
            unmatched=unmatched,
            all_members=all_members,
            ocr_data_map=ocr_data_map,
            image_file=fname,
        )

    return render_template("vice_secretary/upload_attendance.html", today=str(date.today()))

# ── Save OCR Attendance ───────────────────────────────────────────────────────
@vs_bp.route("/attendance/save", methods=["POST"])
@login_required
@vs_required
def save_attendance():
    meeting_date_str = request.form.get("meeting_date")
    meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    present_ids = request.form.getlist("present_ids")
    unmatched_names = request.form.getlist("unmatched_names")
    ocr_data_map = json.loads(request.form.get("ocr_data_map", "{}"))

    # --- Process matched/existing members ---
    for key in request.form:
        if key.startswith("member_"):
            member_id = key.split("_")[1]
            full_name = request.form.get(f"name_{member_id}")
            email = request.form.get(f"email_{member_id}") or f"user_{uuid.uuid4().hex[:6]}@net.org"
            phone = request.form.get(f"phone_{member_id}", "")
            residence = request.form.get(f"residence_{member_id}", "")
            year = request.form.get(f"year_{member_id}", "")

            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    residence=residence,
                    year=year,
                    role="member",
                    is_active=True
                )
                db.session.add(user)
                db.session.flush()

            status = "present" if member_id in present_ids else "absent"
            existing = Attendance.query.filter_by(user_id=user.id, meeting_date=meeting_date).first()
            if existing:
                existing.status = status
            else:
                db.session.add(Attendance(
                    user_id=user.id,
                    meeting_date=meeting_date,
                    status=status,
                    source="ocr_upload",
                    recorded_by=current_user.id
                ))

    # --- Auto-add unmatched names as new members present ---
    for name in unmatched_names:
        name = name.strip()
        if not name:
            continue
        lower_name = name.lower()
        data = ocr_data_map.get(lower_name, {})
        placeholder_email = f"guest_{uuid.uuid4().hex[:6]}@net.org"
        user = User(
            full_name=name,
            email=placeholder_email,
            role="member",
            is_active=True,
            residence=data.get("residence", ""),
            year=data.get("year", "")
        )
        db.session.add(user)
        db.session.flush()

        db.session.add(Attendance(
            user_id=user.id,
            meeting_date=meeting_date,
            status="present",
            source="ocr_upload",
            recorded_by=current_user.id,
            notes="Unmatched name auto-added"
        ))

    db.session.commit()
    flash(f"Attendance for {meeting_date} saved successfully.", "success")
    return redirect(url_for("vs.dashboard"))

# ── Manual Attendance ─────────────────────────────────────────────────────────
@vs_bp.route("/attendance/manual", methods=["GET", "POST"])
@login_required
@vs_required
def manual_attendance():
    members = User.query.filter_by(is_active=True, role="member").order_by(User.full_name).all()
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
                db.session.add(Attendance(
                    user_id=member.id,
                    meeting_date=meeting_date,
                    status=status,
                    source="manual",
                    recorded_by=current_user.id
                ))

        db.session.commit()
        flash("Attendance recorded manually.", "success")
        return redirect(url_for("vs.dashboard"))

    return render_template("vice_secretary/manual_attendance.html", members=members, today=str(date.today()))

# ── Meeting Voice Recording ───────────────────────────────────────────────────
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
    title = request.form.get("title", "Meeting Minutes")

    if not audio_file:
        return jsonify({"error": "No audio file provided"}), 400

    ext = "webm"
    fname = f"meeting_{meeting_date_str}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
    audio_file.save(save_path)

    from services.ai_service import transcribe_audio, summarize_transcript
    transcript = transcribe_audio(save_path)
    summary, action_points = summarize_transcript(transcript)

    meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    minutes = MeetingMinutes(
        meeting_date=meeting_date,
        title=title,
        transcript=transcript,
        summary=summary,
        action_points=json.dumps(action_points),
        audio_file=fname,
        recorded_by=current_user.id
    )
    db.session.add(minutes)
    db.session.commit()

    return jsonify({
        "success": True,
        "minutes_id": minutes.id,
        "transcript": transcript,
        "summary": summary,
        "action_points": action_points
    })

# ── Fuzzy Name Matching ───────────────────────────────────────────────────────
def _fuzzy_match(extracted_names, members):
    matched = []
    unmatched = []
    member_map = {m.full_name.lower(): m for m in members}

    for name in extracted_names:
        name_lower = name.lower().strip()
        found = None

        if name_lower in member_map:
            found = member_map[name_lower]
        else:
            for key, member in member_map.items():
                tokens_extracted = set(name_lower.split())
                tokens_member = set(key.split())
                if len(tokens_extracted & tokens_member) >= 1:
                    found = member
                    break

        if found:
            matched.append({"name": name, "member": found})
        else:
            unmatched.append(name)

    return matched, unmatched