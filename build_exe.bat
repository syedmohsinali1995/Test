@echo off
title AI Real Estate Agent - .exe Builder
color 0A

echo ================================================
echo   AI Real Estate Calling Agent - .exe Builder
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11 from python.org
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
echo      Done.

echo [2/4] Cleaning previous build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
echo      Done.

echo [3/4] Building .exe (this takes 2-5 minutes)...
pyinstaller app.spec --noconfirm --clean
echo      Done.

echo [4/4] Checking output...
if exist dist\RealEstateAI.exe (
    echo.
    echo ================================================
    echo   SUCCESS! .exe file created:
    echo   dist\RealEstateAI.exe
    echo ================================================
    echo.
    echo File size:
    for %%A in (dist\RealEstateAI.exe) do echo %%~zA bytes
    echo.
    echo Give "dist\RealEstateAI.exe" to your client.
    echo They double-click it - done!
) else (
    echo [ERROR] Build failed. Check output above.
)

echo.
pause
