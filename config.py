"""Basic application settings for NoteNest."""

import os


class Config:
    """Settings used by the Flask app and its extensions."""

    SECRET_KEY = os.environ.get("NOTENEST_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = "sqlite:///notenest.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "instance",
        "uploads",
    )
    MAX_UPLOAD_FILE_SIZE = 10 * 1024 * 1024
    MAX_CONTENT_LENGTH = MAX_UPLOAD_FILE_SIZE + (64 * 1024)

    NOTENEST_STORAGE_BACKEND = os.environ.get(
        "NOTENEST_STORAGE_BACKEND",
        "LOCAL",
    ).strip().upper()
    AWS_REGION = os.environ.get("AWS_REGION")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("NOTENEST_COOKIE_SECURE", "").lower() in {
        "1",
        "true",
        "yes",
    }
