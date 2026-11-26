# NoteNest

NoteNest is a student notes sharing platform built with HTML, CSS, JavaScript,
Python Flask, and SQLite.

## Project structure

```text
NoteNest/
|-- app.py
|-- config.py
|-- models.py
|-- storage.py
|-- requirements.txt
|-- README.md
|-- instance/             (created automatically for the database and PDF files)
|-- static/
|   |-- css/
|   |-- images/
|   `-- js/
`-- templates/
    |-- index.html
    |-- explore.html
    |-- home.html
    |-- login.html
    |-- register.html
    |-- dashboard.html
    |-- upload.html
    `-- my_uploads.html
```

## Getting started (PowerShell)

1. Create and activate a Python virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Set a secret key for the current PowerShell session, then start the app:

   ```powershell
   $env:NOTENEST_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in a browser.

The SQLite database and its `user` and `note` tables are created automatically
in the `instance` folder. Uploaded PDFs are kept in `instance/uploads`; the
folder is not served as a public static directory. For an HTTPS deployment,
set `NOTENEST_COOKIE_SECURE=true` so browsers only send the session cookie over
HTTPS.

## Testing authentication and notes

1. Select **Get Started**, enter your name, a valid email address, and a
   password of at least 8 characters twice.
2. Log in using that email and password. A successful login opens the protected
   dashboard. **Explore Notes**, **Upload Notes**, and **My Uploads** are also
   available in the navigation.
3. Open **Upload Notes**, enter a title, subject, semester, and description,
   then select a PDF no larger than 10 MB.
4. Open **Explore Notes** to search by title, filter by subject, and download
   a note. The page shows its uploader and upload date.
5. Open **My Uploads** to download or delete your own notes. Deletion requires
   confirmation and cannot remove another student's note.
6. Use **Log out** to end the session and return home.

Registration validates the email format but does not restrict accounts to a
particular college domain. Uploads require a PDF filename and PDF file
signature, and are stored under a unique safe filename. Passwords are stored
as hashes, and form submissions use CSRF protection. S3 is available as an
optional storage backend; local storage remains the default.

## Optional Amazon S3 storage

The storage backend is selected with environment variables. Local storage is
the default:

```powershell
$env:NOTENEST_STORAGE_BACKEND = "LOCAL"
python app.py
```

To use S3, create an S3 bucket in the AWS region you plan to use. Keep **Block
all public access** enabled, disable ACLs with **Bucket owner enforced**
ownership, and enable the bucket's default encryption. Do not add a public
bucket policy. The application does not set an object ACL or create public
download URLs.

Set the bucket and region before starting the app:

```powershell
$env:NOTENEST_STORAGE_BACKEND = "S3"
$env:AWS_REGION = "your-aws-region"
$env:S3_BUCKET_NAME = "your-unique-bucket-name"
python app.py
```

`boto3` uses its standard AWS credential provider chain. For local development,
use an AWS profile or SSO session (for example, `AWS_PROFILE`) or use an IAM
role when running on AWS. Give that identity only `s3:PutObject`,
`s3:GetObject`, and `s3:DeleteObject` access to
`arn:aws:s3:::your-unique-bucket-name/s3/*`. Never put AWS access keys in
source code.

New S3 object keys are stored with an `s3/` prefix. Existing local storage keys
continue to use `instance/uploads`, so switching to S3 does not remove existing
PDFs. If you later switch back to local mode, keep `AWS_REGION` and
`S3_BUCKET_NAME` configured if the application still needs to download or
delete notes stored in S3. Changing the backend does not copy files between
storage systems.

To test S3, configure a real private bucket and AWS identity, start with the
S3 environment variables above, then upload, explore, download, and delete a
test PDF. AWS connectivity has not been tested as part of this implementation.
