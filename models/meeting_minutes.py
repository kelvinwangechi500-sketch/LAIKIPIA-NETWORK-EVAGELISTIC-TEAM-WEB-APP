from datetime import datetime
from extensions import db

class MeetingMinutes(db.Model):
    __tablename__ = "meeting_minutes"
    id = db.Column(db.Integer, primary_key=True)
    meeting_date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    transcript = db.Column(db.Text)
    summary = db.Column(db.Text)
    action_points = db.Column(db.Text)
    audio_file = db.Column(db.String(300))
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    recorder = db.relationship("User", foreign_keys=[recorded_by], lazy="joined")
