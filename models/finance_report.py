from datetime import datetime

from extensions import db


class FinanceReport(db.Model):
    __tablename__ = "finance_reports"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    opening_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    explanation = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="draft")
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submitter = db.relationship("User", foreign_keys=[submitted_by], lazy="joined")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], lazy="joined")
    __table_args__ = (db.UniqueConstraint("year", "semester", name="uq_finance_report_period"),)