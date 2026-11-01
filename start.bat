@echo off
setlocal EnableExtensions
set PYTHONUTF8=1

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    python main.py %*
) else (
    py -3 --version >nul 2>nul
    if errorlevel 1 (
        python main.py %*
    ) else (
        py -3 main.py %*
    )
)

set "APP_EXIT_CODE=%ERRORLEVEL%"
if "%APP_EXIT_CODE%"=="0" goto :end

echo.
echo Messenger could not be started. See the error above.
pause

:end
exit /b %APP_EXIT_CODE%
