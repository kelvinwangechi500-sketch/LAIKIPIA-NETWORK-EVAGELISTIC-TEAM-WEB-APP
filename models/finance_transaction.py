from datetime import date, datetime
from extensions import db


class FinanceTransaction(db.Model):
    __tablename__ = "finance_transactions"

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    income_type = db.Column(db.String(40), nullable=False, default="Other")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    transaction_date = db.Column(db.Date, nullable=False, default=date.today)
    semester = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(40), default="Cash")
    status = db.Column(db.String(20), nullable=False, default="pending")
    rejection_reason = db.Column(db.String(300))
    receipt_file = db.Column(db.String(300))
    receipt_name = db.Column(db.String(200))
    receipt_mime = db.Column(db.String(120))
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    submitter = db.relationship("User", foreign_keys=[submitted_by], lazy="joined")
    approver = db.relationship("User", foreign_keys=[approved_by], lazy="joined")
