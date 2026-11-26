"""Database models used by NoteNest."""

from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """A student account with a securely hashed password."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    notes = db.relationship("Note", back_populates="uploader")

    def set_password(self, password):
        """Store a one-way hash instead of the original password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check a submitted password against the stored hash."""
        return check_password_hash(self.password_hash, password)


class Note(db.Model):
    """A PDF study note shared by a student."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(80), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    upload_date = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    uploader = db.relationship("User", back_populates="notes")
