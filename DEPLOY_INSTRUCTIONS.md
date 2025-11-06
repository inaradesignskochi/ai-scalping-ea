# 🚀 Oracle Cloud Deployment Instructions
## AI Scalping EA - Production Ready

### Quick Deployment (Windows)
1. **Open Command Prompt as Administrator**
2. **Navigate to this project folder**
3. **Run Phase 1**: Double-click `deploy-oci-phase1.bat`
4. **Wait for completion** and open a new Command Prompt
5. **Run Phase 2**: Double-click `deploy-oci-phase2.bat`

### Manual SSH Deployment
If the batch files don't work, use these manual commands:

#### Phase 1: System Setup
```cmd
ssh -i "C:\Users\anees\.ssh\ssh-key-2025-11-05.key" -o StrictHostKeyChecking=no ubuntu@144.24.149.180
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git curl wget unzip python3-pip nodejs npm
sudo systemctl start docker && sudo systemctl enable docker
sudo usermod -aG docker $USER
exit
```

#### Phase 2: Application Deployment
```cmd
ssh -i "C:\Users\anees\.ssh\ssh-key-2025-11-05.key" ubuntu@144.24.149.180
git clone https://github.com/inaradesignskochi/ai-scalping-ea.git
cd ai-scalping-ea
docker-compose up -d
```

### Access Points (After Deployment)
- **Main Dashboard**: http://144.24.149.180:8501
- **Grafana Monitor**: http://144.24.149.180:3000 (admin/your_grafana_password)
- **Prometheus**: http://144.24.149.180:9090
- **Health Check**: http://144.24.149.180:8000/health

### Your API Keys Configured
✅ Gemini AI API: Configured  
✅ Alpaca Trading API: Configured  
✅ MarketAux API: Configured  
✅ Grafana Password: Configured  
✅ Oracle Cloud IP: 144.24.149.180  

### Next Steps
1. **Run the deployment script**
2. **Access the dashboard** at http://144.24.149.180:8501
3. **Set up MT4 Expert Advisor** from the `mt4/Experts/` folder
4. **Start paper trading** for 30 days testing
5. **Monitor performance** via Grafana dashboards

### Support
If you encounter issues, check:
- Docker service status: `docker ps`
- Service logs: `docker-compose logs -f`
- Health check: `curl http://localhost:8000/health`