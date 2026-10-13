@echo off
setlocal
cd /d "%~dp0\.."

echo ======================================================================
echo   Budowanie obrazu TVDecoder OS (Hybrid ISO) za pomoca WSL
echo ======================================================================
echo.

where wsl >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [BLAD] WSL nie jest zainstalowany!
    pause
    exit /b 1
)

echo Konwertowanie sciezki do formatu WSL i uruchamianie skryptu...
wsl sudo bash -c "cd $(wslpath '%cd%') && chmod +x scripts/build_iso.sh && ./scripts/build_iso.sh"

if exist TVDecoderOS.iso (
    echo.
    echo ======================================================================
    echo   SUKCES! Wygenerowano plik: TVDecoderOS.iso
    echo ======================================================================
) else (
    echo.
    echo [BLAD] Budowanie nie powiodlo sie.
)

pause
