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

rem Prompt the user for a commit message
set /p commitMessage=Enter commit message: 

rem Check if the commit message is empty
if "%commitMessage%"=="" (
    echo Commit message cannot be empty.
    pause
    exit /b 1
)

rem Stage all changes
git add --all

rem Commit with the user's message
git commit -m "%commitMessage%"

rem Push to the main branch
git push origin main

rem Indicate completion
echo Changes have been staged, committed, and pushed to the main branch.
pause
