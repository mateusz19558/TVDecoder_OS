@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo    Wysylanie TVDecoder OS do GitHub: mateusz19558/TVDecoder_OS
echo ======================================================================
echo.

set "PATH=%LOCALAPPDATA%\MinGit\cmd;%PATH%"

git remote set-url origin https://github.com/mateusz19558/TVDecoder_OS.git

echo Rozpoczynam wysylanie brancha main...
echo (Jesli pojawi sie monit logowania GitHub w przegladarce, zatwierdz go).
echo.
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo   SUKCES! Kod zostal wyslany na GitHub!
    echo   Budowanie ISO uruchomilo sie automatycznie w zakladce Actions:
    echo   https://github.com/mateusz19558/TVDecoder_OS/actions
    echo ======================================================================
) else (
    echo.
    echo [UWAGA] Wystapil problem z autoryzacja. Upewnij sie, ze jestes zalogowany na GitHubie.
)

pause
