@echo off
set "PATH=%PATH%;C:\Program Files\GitHub CLI"
echo ============================================================
echo   RELINK AI -- Automatic GitHub Creator and Uploader
echo ============================================================
echo.

git add .
git commit -m "Deploy Relink AI: clean production release" >nul 2>&1

gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/2] GitHub login required (One-time setup).
    echo       Opening browser for authorization...
    echo.
    gh auth login -w -p https
)

echo.
echo [2/2] Creating remote repository 'relink-ai' on your GitHub and pushing code...
echo.
gh repo create relink-ai --public --source=. --remote=origin --push

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   [SUCCESS] Relink AI aapke GitHub par upload ho gaya hai!
    echo ============================================================
) else (
    echo.
    echo Repository check: pushing to origin...
    git push -u origin master
)

echo.
pause
