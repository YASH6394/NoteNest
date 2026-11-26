"""Local and Amazon S3 storage implementations for note PDFs."""

import io
import os
import re
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from werkzeug.utils import secure_filename


class UploadValidationError(ValueError):
    """Raised when an uploaded file is not an acceptable PDF."""


class StorageOperationError(RuntimeError):
    """Raised when a configured storage backend cannot complete an operation."""


def _read_valid_pdf(uploaded_file, max_size):
    """Validate the filename, file size, and PDF content before storing it."""
    safe_original_name = secure_filename(uploaded_file.filename or "")
    if not safe_original_name:
        raise UploadValidationError("Choose a PDF file to upload.")
    if not safe_original_name.lower().endswith(".pdf"):
        raise UploadValidationError("Only PDF files are allowed.")

    content = uploaded_file.stream.read(max_size + 1)
    if not content:
        raise UploadValidationError("The selected file is empty.")
    if len(content) > max_size:
        raise UploadValidationError("The PDF must be 10 MB or smaller.")
    if b"%PDF-" not in content[:1024] or b"%%EOF" not in content[-1024:]:
        raise UploadValidationError("The selected file does not appear to be a valid PDF.")

    return content


def _new_local_filename():
    return secure_filename(f"{uuid.uuid4().hex}.pdf")


class LocalFileStorage:
    """Save and retrieve PDFs without exposing their server-side paths."""

    def __init__(self, upload_folder):
        self.upload_folder = upload_folder

    def save(self, uploaded_file, max_size):
        """Validate a PDF and save it under a unique, safe storage key."""
        content = _read_valid_pdf(uploaded_file, max_size)
        os.makedirs(self.upload_folder, exist_ok=True)

        for _ in range(3):
            stored_filename = _new_local_filename()
            destination = os.path.join(self.upload_folder, stored_filename)
            try:
                with open(destination, "xb") as saved_file:
                    saved_file.write(content)
            except FileExistsError:
                continue
            return stored_filename

        raise OSError("Could not create a unique filename for the uploaded PDF.")

    def open(self, stored_filename):
        """Open an existing PDF using its internal storage key."""
        return open(self._get_path(stored_filename), "rb")

    def delete(self, stored_filename):
        """Remove a PDF if it still exists in local storage."""
        try:
            os.remove(self._get_path(stored_filename))
        except FileNotFoundError:
            pass

    def _get_path(self, stored_filename):
        safe_filename = secure_filename(stored_filename or "")
        if safe_filename != stored_filename or not safe_filename.lower().endswith(".pdf"):
            raise FileNotFoundError
        return os.path.join(self.upload_folder, safe_filename)


class S3FileStorage:
    """Store PDFs in a private S3 bucket using boto3's credential chain."""

    STORAGE_PREFIX = "s3/"
    KEY_PATTERN = re.compile(r"s3/[0-9a-f]{32}\.pdf\Z")

    def __init__(self, bucket_name, region_name, s3_client=None):
        self.bucket_name = bucket_name
        self.client = s3_client or boto3.client("s3", region_name=region_name)

    def save(self, uploaded_file, max_size):
        """Upload a validated PDF without adding a public ACL."""
        content = _read_valid_pdf(uploaded_file, max_size)

        for _ in range(3):
            key = f"{self.STORAGE_PREFIX}{uuid.uuid4().hex}.pdf"
            try:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content,
                    ContentType="application/pdf",
                    IfNoneMatch="*",
                )
            except ClientError as error:
                error_code = error.response.get("Error", {}).get("Code")
                if error_code in {
                    "PreconditionFailed",
                    "412",
                    "ConditionalRequestConflict",
                    "409",
                }:
                    continue
                raise StorageOperationError("Could not upload the PDF to S3.") from error
            except BotoCoreError as error:
                raise StorageOperationError("Could not upload the PDF to S3.") from error
            return key

        raise StorageOperationError("Could not create a unique S3 object key.")

    def open(self, stored_filename):
        """Read a PDF from S3 into a file-like object for Flask to send."""
        key = self._validate_key(stored_filename)
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            body = response["Body"]
            try:
                return io.BytesIO(body.read())
            finally:
                body.close()
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "NotFound", "404"}:
                raise FileNotFoundError from error
            raise StorageOperationError("Could not download the PDF from S3.") from error
        except BotoCoreError as error:
            raise StorageOperationError("Could not download the PDF from S3.") from error

    def delete(self, stored_filename):
        """Delete a PDF object from S3."""
        key = self._validate_key(stored_filename)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Could not delete the PDF from S3.") from error

    def _validate_key(self, stored_filename):
        if not isinstance(stored_filename, str) or not self.KEY_PATTERN.fullmatch(stored_filename):
            raise FileNotFoundError
        return stored_filename


class ConfigurableStorage:
    """Route new uploads to one backend and existing keys to their own backend."""

    def __init__(self, primary, local_storage, s3_storage=None):
        self.primary = primary
        self.local_storage = local_storage
        self.s3_storage = s3_storage

    def save(self, uploaded_file, max_size):
        return self.primary.save(uploaded_file, max_size)

    def open(self, stored_filename):
        if stored_filename.startswith(S3FileStorage.STORAGE_PREFIX):
            return self._get_s3_storage().open(stored_filename)
        return self.local_storage.open(stored_filename)

    def delete(self, stored_filename):
        if stored_filename.startswith(S3FileStorage.STORAGE_PREFIX):
            self._get_s3_storage().delete(stored_filename)
        else:
            self.local_storage.delete(stored_filename)

    def _get_s3_storage(self):
        if self.s3_storage is None:
            raise StorageOperationError(
                "S3 settings are required to access this previously uploaded note."
            )
        return self.s3_storage


def create_storage(config):
    """Build the selected upload backend and readers for existing stored files."""
    backend = str(config.get("NOTENEST_STORAGE_BACKEND", "LOCAL")).strip().upper()
    if backend not in {"LOCAL", "S3"}:
        raise RuntimeError("NOTENEST_STORAGE_BACKEND must be either LOCAL or S3.")

    local_storage = LocalFileStorage(config["UPLOAD_FOLDER"])
    bucket_name = config.get("S3_BUCKET_NAME")
    region_name = config.get("AWS_REGION")

    if backend == "S3" and (not bucket_name or not region_name):
        raise RuntimeError(
            "Set AWS_REGION and S3_BUCKET_NAME when NOTENEST_STORAGE_BACKEND is S3."
        )

    s3_storage = None
    if bucket_name and region_name:
        s3_storage = S3FileStorage(bucket_name, region_name)

    primary = s3_storage if backend == "S3" else local_storage
    return ConfigurableStorage(primary, local_storage, s3_storage)
