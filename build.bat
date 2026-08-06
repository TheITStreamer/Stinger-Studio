@echo off
REM ============================================================
REM  Stinger Studio - build script (Windows) - verbose edition
REM  Writes a full log to build_log.txt so nothing scrolls past.
REM ============================================================
setlocal enabledelayedexpansion
set LOG=build_log.txt
echo Stinger Studio build started %DATE% %TIME% > "%LOG%"

echo.
echo === Stinger Studio build ===
echo (full details are being written to build_log.txt)
echo.

REM --- 0. confirm we are in the right folder ---
if not exist "app.py" (
  echo [X] app.py not found in this folder.
  echo     Make sure build.bat is in the SAME folder as app.py, engine.py, ui.html.
  echo [X] app.py not found >> "%LOG%"
  goto :fail
)

REM --- 1. find a working Python launcher ---
set PY=
where py >nul 2>&1 && set PY=py
if "!PY!"=="" (
  where python >nul 2>&1 && set PY=python
)
if "!PY!"=="" (
  echo [X] Python not found. Install from python.org and tick "Add python.exe to PATH".
  echo [X] no python >> "%LOG%"
  goto :fail
)
echo [OK] Using Python launcher: !PY!
!PY! --version >> "%LOG%" 2>&1
!PY! --version

REM --- 2. install deps (log everything) ---
echo.
echo Installing packages (this can take a minute)...
!PY! -m pip install --upgrade pip >> "%LOG%" 2>&1
!PY! -m pip install pillow numpy pywebview pyinstaller >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [X] pip install failed. See build_log.txt for the reason.
  goto :fail
)
echo [OK] Packages installed.

REM --- 2b. verify pyinstaller is actually importable ---
!PY! -m PyInstaller --version >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [X] PyInstaller did not install correctly. See build_log.txt.
  goto :fail
)
for /f %%v in ('!PY! -m PyInstaller --version 2^>nul') do echo [OK] PyInstaller %%v

REM --- 3. fetch ffmpeg into .\bin if missing ---
if exist "bin\ffmpeg.exe" (
  echo [OK] ffmpeg already present in bin\.
  echo ffmpeg present >> "%LOG%"
) else (
  echo.
  echo Downloading ffmpeg ^(one time, ~80MB^)...
  !PY! fetch_ffmpeg.py >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [X] ffmpeg download failed. See build_log.txt.
    echo     Manual fix: put an ffmpeg.exe into a folder named "bin" next to this script.
    goto :fail
  )
  echo [OK] ffmpeg ready.
)

REM --- 4. build ---
echo.
echo Building the exe with PyInstaller...
!PY! -m PyInstaller --noconfirm --clean StingerStudio.spec >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [X] PyInstaller build failed. See build_log.txt for the traceback.
  goto :fail
)

REM --- 5. confirm the exe exists ---
if exist "dist\StingerStudio.exe" (
  echo.
  echo ============================================================
  echo  SUCCESS. Your app is at:  dist\StingerStudio.exe
  echo  Hand that single file to anyone - they run it, no install.
  echo ============================================================
  echo SUCCESS >> "%LOG%"
) else (
  echo [X] Build reported success but dist\StingerStudio.exe is missing.
  echo     Open build_log.txt and look near the end for "WARNING" or "ERROR".
  echo missing exe after build >> "%LOG%"
  goto :fail
)

echo.
echo Press any key to close.
pause >nul
exit /b 0

:fail
echo.
echo Build did NOT complete. Open build_log.txt in this folder and send it over.
echo.
echo Press any key to close.
pause >nul
exit /b 1
