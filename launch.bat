@echo off
title AGENT PRAYATH v2.0
echo [>>>] Launching Agent Prayath (Automatic Code Editor)...
python vision_agent.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] An error occurred. Check error_log.txt for details.
    pause
)
