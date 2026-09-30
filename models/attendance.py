from datetime import datetime
from extensions import db

class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    meeting_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="present")
    source = db.Column(db.String(30), default="manual")
    notes = db.Column(db.Text, default="")
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recorder = db.relationship("User", foreign_keys=[recorded_by], lazy="joined")
    __table_args__ = (db.UniqueConstraint("user_id", "meeting_date", name="uq_user_date"),)
