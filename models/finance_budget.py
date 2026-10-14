from datetime import datetime

from extensions import db


class FinanceBudget(db.Model):
    __tablename__ = "finance_budgets"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by], lazy="joined")
    __table_args__ = (db.UniqueConstraint("year", "semester", "category", name="uq_budget_period_category"),)