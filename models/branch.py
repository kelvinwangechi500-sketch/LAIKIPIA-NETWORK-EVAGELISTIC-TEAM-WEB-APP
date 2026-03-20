"""
Branch / Chapter Model
"""

from datetime import datetime
from extensions import db


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    location = db.Column(db.String(200))
    leader_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship("User", backref="branch", lazy="dynamic")
