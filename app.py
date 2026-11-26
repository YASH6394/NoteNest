"""Application entry point for NoteNest."""

import os

from email_validator import EmailNotValidError, validate_email
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from config import Config
from models import Note, User, db
from storage import (
    StorageOperationError,
    UploadValidationError,
    create_storage,
)

NOTE_SUBJECTS = (
    "Database Management System",
    "Data Structures",
    "Operating Systems",
    "Python Programming",
    "Data Science",
    "Computer Networks",
)
SEMESTERS = tuple(str(number) for number in range(1, 9))

app = Flask(__name__)
app.config.from_object(Config)

if not app.config.get("SECRET_KEY"):
    raise RuntimeError(
        "Set the NOTENEST_SECRET_KEY environment variable before starting NoteNest."
    )

os.makedirs(app.instance_path, exist_ok=True)

db.init_app(app)
storage = create_storage(app.config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to view that page."
login_manager.session_protection = "strong"

csrf = CSRFProtect()
csrf.init_app(app)


@app.errorhandler(RequestEntityTooLarge)
def handle_large_request(error):
    """Show an upload-specific message when the request body exceeds its limit."""
    if request.path == "/upload":
        flash("The PDF must be 10 MB or smaller.", "error")
        return redirect(url_for("upload_note"))
    return "The request is too large.", 413


@login_manager.user_loader
def load_user(user_id):
    """Load a user from the ID stored in the signed session."""
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@app.route("/")
def home():
    """Display the NoteNest home page."""
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Create an account after validating the submitted details."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        errors = []

        if not full_name:
            errors.append("Please enter your full name.")
        elif len(full_name) > 120:
            errors.append("Your full name must be 120 characters or fewer.")

        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            errors.append("Please enter a valid college email address.")

        if not password:
            errors.append("Please enter a password.")
        elif len(password) < 8:
            errors.append("Your password must be at least 8 characters long.")
        elif len(password) > 128:
            errors.append("Your password must be 128 characters or fewer.")

        if not confirm_password:
            errors.append("Please confirm your password.")
        elif password != confirm_password:
            errors.append("The passwords do not match.")

        if not errors and User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
        else:
            user = User(full_name=full_name, email=email)
            user.set_password(password)
            db.session.add(user)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("An account with that email already exists.", "error")
            else:
                flash("Your account is ready. Please log in.", "success")
                return redirect(url_for("login"))

        return render_template(
            "register.html",
            full_name=full_name,
            email=email,
        )

    return render_template("register.html", full_name="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an existing student."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first() if email else None

        if user is None or not user.check_password(password):
            flash("Email or password is incorrect.", "error")
            return render_template("login.html", email=email)

        session.clear()
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html", email="")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    """End the current user's session."""
    logout_user()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Display the protected student dashboard."""
    return render_template("dashboard.html")


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_note():
    """Validate a note and save its PDF before adding its database record."""
    form_data = {
        "title": request.form.get("title", "").strip(),
        "subject": request.form.get("subject", ""),
        "semester": request.form.get("semester", ""),
        "description": request.form.get("description", "").strip(),
    }

    if request.method == "POST":
        errors = []
        if not form_data["title"]:
            errors.append("Enter a title for your note.")
        elif len(form_data["title"]) > 120:
            errors.append("The title must be 120 characters or fewer.")

        if form_data["subject"] not in NOTE_SUBJECTS:
            errors.append("Choose a subject from the list.")

        if form_data["semester"] not in SEMESTERS:
            errors.append("Choose a semester from the list.")

        if not form_data["description"]:
            errors.append("Add a short description for your note.")
        elif len(form_data["description"]) > 500:
            errors.append("The description must be 500 characters or fewer.")

        uploaded_file = request.files.get("pdf_file")
        if uploaded_file is None or not uploaded_file.filename:
            errors.append("Choose a PDF file to upload.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "upload.html",
                subjects=NOTE_SUBJECTS,
                semesters=SEMESTERS,
                form_data=form_data,
            ), 400

        try:
            stored_filename = storage.save(
                uploaded_file,
                app.config["MAX_UPLOAD_FILE_SIZE"],
            )
        except UploadValidationError as error:
            flash(str(error), "error")
            return render_template(
                "upload.html",
                subjects=NOTE_SUBJECTS,
                semesters=SEMESTERS,
                form_data=form_data,
            ), 400
        except (OSError, StorageOperationError):
            app.logger.exception("Could not store an uploaded PDF.")
            flash("The PDF could not be saved. Please try again.", "error")
            return render_template(
                "upload.html",
                subjects=NOTE_SUBJECTS,
                semesters=SEMESTERS,
                form_data=form_data,
            ), 500

        note = Note(
            title=form_data["title"],
            subject=form_data["subject"],
            semester=form_data["semester"],
            description=form_data["description"],
            filename=stored_filename,
            uploader_id=current_user.id,
        )
        db.session.add(note)

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Could not save uploaded note metadata.")
            try:
                storage.delete(stored_filename)
            except (OSError, StorageOperationError):
                app.logger.exception("Could not clean up an unlinked PDF.")
            flash("Your note could not be saved. Please try again.", "error")
            return render_template(
                "upload.html",
                subjects=NOTE_SUBJECTS,
                semesters=SEMESTERS,
                form_data=form_data,
            ), 500

        flash("Your note was uploaded.", "success")
        return redirect(url_for("my_uploads"))

    return render_template(
        "upload.html",
        subjects=NOTE_SUBJECTS,
        semesters=SEMESTERS,
        form_data=form_data,
    )


@app.route("/notes")
@login_required
def explore_notes():
    """List uploaded notes with optional title and subject filters."""
    search = request.args.get("search", "").strip()[:120]
    selected_subject = request.args.get("subject", "")
    if selected_subject not in NOTE_SUBJECTS:
        selected_subject = ""

    query = Note.query.options(joinedload(Note.uploader))
    if search:
        query = query.filter(Note.title.ilike(f"%{search}%"))
    if selected_subject:
        query = query.filter_by(subject=selected_subject)

    notes = query.order_by(Note.upload_date.desc()).all()
    return render_template(
        "explore.html",
        notes=notes,
        subjects=NOTE_SUBJECTS,
        search=search,
        selected_subject=selected_subject,
    )


@app.route("/my-uploads")
@login_required
def my_uploads():
    """Show only the notes uploaded by the signed-in student."""
    notes = (
        Note.query.filter_by(uploader_id=current_user.id)
        .order_by(Note.upload_date.desc())
        .all()
    )
    return render_template("my_uploads.html", notes=notes)


@app.route("/notes/<int:note_id>/download")
@login_required
def download_note(note_id):
    """Send a note PDF as an attachment without exposing its storage path."""
    note = Note.query.get_or_404(note_id)
    try:
        pdf_file = storage.open(note.filename)
    except FileNotFoundError:
        abort(404)
    except StorageOperationError:
        app.logger.exception("Could not retrieve a note PDF.")
        flash("The PDF is temporarily unavailable. Please try again later.", "error")
        return redirect(url_for("explore_notes"))

    download_name = secure_filename(f"{note.title}.pdf") or "study-note.pdf"
    return send_file(
        pdf_file,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id):
    """Delete a note only when it belongs to the signed-in student."""
    note = Note.query.filter_by(
        id=note_id,
        uploader_id=current_user.id,
    ).first_or_404()
    stored_filename = note.filename
    db.session.delete(note)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not delete note metadata.")
        flash("Your note could not be deleted. Please try again.", "error")
        return redirect(url_for("my_uploads"))

    try:
        storage.delete(stored_filename)
    except (OSError, StorageOperationError):
        app.logger.exception("Could not remove a deleted note's PDF.")
        flash("The note was removed, but its PDF could not be cleaned up.", "error")
    else:
        flash("Your note was deleted.", "success")

    return redirect(url_for("my_uploads"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
