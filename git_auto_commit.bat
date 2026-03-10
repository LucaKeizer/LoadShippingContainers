@echo off
rem Navigate to the folder where the script is located
cd /d "%~dp0"

rem Check if this is a Git repository
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo This is not a Git repository.
    pause
    exit /b 1
)

rem Stage all changes
git add --all

rem Commit with a default message
git commit -m "Automated commit"

rem Push to the main branch
git push origin main

rem Indicate completion
echo Changes have been staged, committed, and pushed to the main branch.
pause
