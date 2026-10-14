from datetime import date, datetime

from extensions import db


class FinanceAsset(db.Model):
    __tablename__ = "finance_assets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    purchase_amount = db.Column(db.Numeric(12, 2), nullable=False)
    purchase_date = db.Column(db.Date, nullable=False, default=date.today)
    condition = db.Column(db.String(40), default="Good")
    location = db.Column(db.String(150))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by], lazy="joined")