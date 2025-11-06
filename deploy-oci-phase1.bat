@echo off
REM 🚀 AI Scalping EA - Oracle Cloud Deployment Script (Windows)
REM This script will deploy your complete AI Scalping EA system to OCI

echo 🚀 Starting AI Scalping EA deployment to Oracle Cloud...
echo Target: ubuntu@144.24.149.180
echo ==================================================

REM Set SSH key path (update this if needed)
SET SSH_KEY_PATH=C:\Users\anees\.ssh\ssh-key-2025-11-05.key

REM Check if SSH key exists
IF NOT EXIST "%SSH_KEY_PATH%" (
    echo ❌ Error: SSH key not found at %SSH_KEY_PATH%
    echo Please update the SSH_KEY_PATH variable in this script with the correct path
    pause
    exit /b 1
)

echo ✅ SSH key found at %SSH_KEY_PATH%

REM Test SSH connection
echo 🔌 Testing SSH connection...
ssh -i "%SSH_KEY_PATH%" -o StrictHostKeyChecking=no ubuntu@144.24.149.180 whoami
IF %ERRORLEVEL% NEQ 0 (
    echo ❌ SSH connection failed. Please check:
    echo 1. SSH key path is correct: %SSH_KEY_PATH%
    echo 2. Username is correct: ubuntu
    echo 3. IP address is correct: 144.24.149.180
    echo 4. OCI instance is running and accessible
    pause
    exit /b 1
)

echo ✅ SSH connection successful!

REM Phase 1: System setup
echo 📦 Running Phase 1: System setup...
ssh -i "%SSH_KEY_PATH%" ubuntu@144.24.149.180 << EOF
echo Starting system setup...
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git curl wget unzip python3-pip nodejs npm
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker \$USER
echo ✅ System setup complete
echo Please log out and back in for Docker permissions to take effect
exit
EOF

echo.
echo 🎯 Phase 1 Complete!
echo.
echo NEXT STEPS:
echo 1. Open a NEW Command Prompt or PowerShell window
echo 2. Navigate to this directory
echo 3. Run: deploy-oci-phase2.bat
echo.
pause