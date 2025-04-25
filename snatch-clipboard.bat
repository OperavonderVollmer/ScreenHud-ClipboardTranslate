@echo off
setlocal

cd /d "%~dp0"

title Snatch-Clipboard


call ".\.venv\Scripts\activate.bat"

python ".\ClipboardTranslate\ClipboardSnatch.py"
