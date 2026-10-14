from datetime import date, datetime

from extensions import db


class FinanceObligation(db.Model):
    __tablename__ = "finance_obligations"

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(300), nullable=False)
    obligation_type = db.Column(db.String(30), nullable=False, default="Commitment")
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    due_date = db.Column(db.Date)
    semester = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="outstanding")
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by], lazy="joined")