@echo off
REM setup_psu_server.bat - Automate PSU server deployment to Luckfox device (Windows)
REM Usage: setup_psu_server.bat [DEVICE_IP] [PASSWORD]

setlocal enabledelayedexpansion
set REMOTE_DIR=/opt/psu_controller
set SERVICE_NAME=psucontroller
set PYTHON_FILE=web_server.py
set SCRIPT_DIR=%~dp0
set DEVICE_IP=%1
set PASSWORD=%2

REM --- Detect Luckfox device if not provided ---
if "%DEVICE_IP%"=="" (
    echo Scanning for Luckfox device on local network...
    for /L %%I in (2,1,254) do (
        set IP=192.168.0.%%I
        for /f %%R in ('"plink -batch -pw %PASSWORD% root@!IP! uname -a 2>nul"') do (
            echo %%R | find /I "luckfox" >nul && set DEVICE_IP=!IP! && goto :found
        )
    )
    :found
    if "%DEVICE_IP%"=="" (
        echo [ERROR] Could not auto-detect Luckfox device. Specify IP as first argument.
        exit /b 1
    )
    echo [INFO] Luckfox device found at %DEVICE_IP%
)

if "%PASSWORD%"=="" set PASSWORD=luckfox

REM --- Upload files ---
echo [INFO] Uploading files to %DEVICE_IP%:%REMOTE_DIR% ...
plink -batch -pw %PASSWORD% root@%DEVICE_IP% "mkdir -p %REMOTE_DIR%"
pscp -pw %PASSWORD% -r "%SCRIPT_DIR%*" root@%DEVICE_IP%:%REMOTE_DIR%/

REM --- Setup systemd service ---
set SERVICE_FILE=/etc/systemd/system/%SERVICE_NAME%.service
set SERVICE_CONTENT=[Unit]^\nDescription=PSU Controller Web Server^\nAfter=network.target^\n^\n[Service]^\nType=simple^\nWorkingDirectory=%REMOTE_DIR%^\nExecStart=/usr/bin/python3 %REMOTE_DIR%/%PYTHON_FILE%^\nRestart=always^\nUser=root^\n^\n[Install]^\nWantedBy=multi-user.target^\n

REM Write service file and start service
plink -batch -pw %PASSWORD% root@%DEVICE_IP% "echo %SERVICE_CONTENT% > %SERVICE_FILE% && systemctl daemon-reload && systemctl enable %SERVICE_NAME% && systemctl restart %SERVICE_NAME%"

echo [INFO] Setup complete. Service '%SERVICE_NAME%' is running on %DEVICE_IP%.
endlocal
