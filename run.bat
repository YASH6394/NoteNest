@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto project_directory_error

echo NoteNest is starting...

python --version >nul 2>&1
if errorlevel 1 goto python_missing

if not exist "requirements.txt" goto requirements_missing

if not exist ".venv\Scripts\python.exe" (
    echo Creating the virtual environment...
    python -m venv .venv
    if errorlevel 1 goto venv_creation_failed
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto venv_activation_failed

echo Checking and installing any missing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto dependencies_failed

if not defined NOTENEST_SECRET_KEY (
    for /f "delims=" %%K in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "NOTENEST_SECRET_KEY=%%K"
)
if not defined NOTENEST_SECRET_KEY goto secret_key_failed

if not defined NOTENEST_STORAGE_BACKEND set "NOTENEST_STORAGE_BACKEND=LOCAL"
if /I "%NOTENEST_STORAGE_BACKEND%"=="LOCAL" goto storage_backend_valid
if /I "%NOTENEST_STORAGE_BACKEND%"=="S3" goto check_s3_settings
echo ERROR: NOTENEST_STORAGE_BACKEND must be LOCAL or S3.
goto failed

:check_s3_settings
if not defined AWS_REGION (
    echo ERROR: AWS_REGION is required when using S3 storage.
    goto failed
)
if not defined S3_BUCKET_NAME (
    echo ERROR: S3_BUCKET_NAME is required when using S3 storage.
    goto failed
)

:storage_backend_valid
echo Starting the Flask application...
start "" /b python app.py
if errorlevel 1 goto server_launch_failed

powershell -NoProfile -Command "$ready = $false; for ($attempt = 0; $attempt -lt 30 -and -not $ready; $attempt++) { try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -UseBasicParsing -TimeoutSec 1; if ($response.StatusCode -eq 200) { $ready = $true } } catch { }; if (-not $ready) { Start-Sleep -Seconds 1 } }; if ($ready) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 goto server_start_failed

:server_ready
echo Open http://127.0.0.1:5000 in your browser.
start "" "http://127.0.0.1:5000"
echo.
echo NoteNest is running. Keep this window open while you use the app.

powershell -NoProfile -Command "$failed = 0; while ($failed -lt 5) { try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -UseBasicParsing -TimeoutSec 2; if ($response.StatusCode -eq 200) { $failed = 0 } else { $failed++ } } catch { $failed++ }; if ($failed -lt 5) { Start-Sleep -Seconds 2 } }; exit 1" >nul 2>&1
goto server_stopped

:python_missing
echo ERROR: Python was not found. Install Python 3 and make sure it is on PATH.
goto failed

:requirements_missing
echo ERROR: requirements.txt was not found in the NoteNest project folder.
goto failed

:venv_creation_failed
echo ERROR: The virtual environment could not be created.
goto failed

:venv_activation_failed
echo ERROR: The virtual environment could not be activated.
goto failed

:dependencies_failed
echo ERROR: Dependencies could not be installed. Check your internet connection and try again.
goto failed

:secret_key_failed
echo ERROR: A Flask secret key could not be generated.
goto failed

:server_launch_failed
echo ERROR: The Flask application could not be started.
goto failed

:server_start_failed
echo ERROR: NoteNest did not become available at http://127.0.0.1:5000.
echo Check the error messages above. Another application may already be using port 5000.
goto failed

:server_stopped
echo NoteNest has stopped responding or the Flask process has exited.
echo Check the Flask messages above for details.
pause
exit /b 1

:project_directory_error
echo ERROR: Could not switch to the NoteNest project directory.
goto failed

:failed
echo.
pause
exit /b 1
