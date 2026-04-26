@echo off
setlocal enabledelayedexpansion

REM Build script for Windows using PyInstaller

set ROOT_DIR=%~dp0..
cd /d "%ROOT_DIR%"

set DIST_DIR=%ROOT_DIR%\dist
set SPEC_FILE=%ROOT_DIR%\media_tools.spec
set PYINSTALLER_CONFIG_DIR=%ROOT_DIR%\build\pyinstaller-cache

REM Clean previous builds
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%ROOT_DIR%\build" rmdir /s /q "%ROOT_DIR%\build"

REM Run PyInstaller
python -m PyInstaller --clean --noconfirm "%SPEC_FILE%"

echo Build complete! The results are available in: %DIST_DIR%
echo Executable: %DIST_DIR%\media-tools.exe (or media-tools folder)
echo You can create a ZIP archive for distribution.