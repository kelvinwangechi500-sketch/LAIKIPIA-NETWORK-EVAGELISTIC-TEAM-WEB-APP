"""
Meeting Minutes Model
======================
Stores AI-generated meeting summaries and transcripts.
"""

from datetime import datetime
from extensions import db


class MeetingMinutes(db.Model):
    __tablename__ = "meeting_minutes"

    id = db.Column(db.Integer, primary_key=True)
    meeting_date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    transcript = db.Column(db.Text)          # raw speech-to-text
    summary = db.Column(db.Text)             # AI-generated summary
    action_points = db.Column(db.Text)       # AI-extracted action items (JSON string)
    audio_file = db.Column(db.String(300))   # path to stored audio
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
