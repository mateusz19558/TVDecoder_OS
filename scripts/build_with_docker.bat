@echo off
setlocal
cd /d "%~dp0\.."

echo ======================================================================
echo   Budowanie obrazu TVDecoder OS (Hybrid ISO) za pomoca Dockera
echo ======================================================================
echo.

where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [BLAD] Docker nie jest zainstalowany lub uruchomiony!
    echo Uruchom Docker Desktop lub skorzystaj z GitHub Actions / WSL.
    pause
    exit /b 1
)

echo [1/2] Budowanie srodowiska budujacego...
docker build -t tvdecoder-iso-builder -f scripts/Dockerfile scripts/
if %ERRORLEVEL% neq 0 (
    echo [BLAD] Nie udalo sie zbudowac kontenera Docker!
    pause
    exit /b 1
)

echo.
echo [2/2] Budowanie obrazu ISO (moze zajac kilka minut)...
docker run --rm --privileged -v "%cd%:/workspace" tvdecoder-iso-builder

if exist TVDecoderOS.iso (
    echo.
    echo ======================================================================
    echo   SUKCES! Wygenerowano plik: TVDecoderOS.iso
    echo   Mozesz nagrac go na pendrive programem Rufus lub Ventoy!
    echo ======================================================================
) else (
    echo.
    echo [BLAD] Nie znaleziono wygenerowanego pliku TVDecoderOS.iso.
)

pause
