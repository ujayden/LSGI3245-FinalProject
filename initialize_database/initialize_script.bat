@echo off
setlocal

set "answer="
set /p "answer=Are you sure want to start import? [y/N] "
if /I not "%answer%"=="y" (
    echo Import cancelled.
    pause
    exit /b 0
)

echo Ready to start import.
pause