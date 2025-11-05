# 🚀 AI Scalping EA - Setup Guide

This guide will walk you through setting up the AI Scalping EA system from scratch.

## Prerequisites

### System Requirements
- **Oracle Cloud Account** with Always Free tier
- **MetaTrader 4** terminal installed on Windows
- **GitHub Account** for CI/CD
- **Docker Hub Account** for container registry

### Software Requirements
- Docker & Docker Compose
- Git
- SSH client
- Python 3.11+ (for local development)

## 1. Oracle Cloud Setup

### Create Always Free Instance
1. Go to [Oracle Cloud](https://cloud.oracle.com)
2. Create a free account
3. Launch Ubuntu 22.04 instance (Ampere A1, 4 OCPU, 24GB RAM)
4. Configure security list:
   - SSH (22)
   - HTTP (80)
   - HTTPS (443)
   - ZMQ Signals (5555)
   - ZMQ Heartbeat (5556)
   - Streamlit (8501)
   - Grafana (3000)
   - Prometheus (9090)

### Initial Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Git
sudo apt install git -y

# Clone repository
git clone https://github.com/yourusername/ai-scalping-ea.git
cd ai-scalping-ea
```

## 2. Environment Configuration

### Copy Environment Template
```bash
cp .env.example .env
```

### Edit Environment Variables
```bash
nano .env
```

Configure the following key variables:
```bash
# Database
DB_PASSWORD=your_secure_password_here

# AI APIs (get from respective providers)
GEMINI_API_KEY=your_gemini_api_key
ALPACA_API_KEY=your_alpaca_api_key
MARKETAUX_API_KEY=your_marketaux_api_key

# Monitoring
GRAFANA_PASSWORD=your_grafana_password

# Oracle Cloud IP (replace with your instance IP)
# This will be used by MT4 to connect
ORACLE_IP=your_oracle_cloud_ip
```

## 3. Deploy the System

### Using Deployment Script
```bash
# Make script executable
chmod +x scripts/deploy.sh

# Run full deployment (build, push, deploy)
./scripts/deploy.sh --all
```

### Manual Deployment
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Initialize database
docker-compose exec postgres psql -U trader -d trading_db -f /app/init.sql
```

### Verify Deployment
```bash
# Check service health
docker-compose ps

# Check logs
docker-compose logs ai_backend
docker-compose logs streamlit

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8501
```

## 4. MT4 Setup (Windows Machine)

### Download and Install MT4
1. Download MT4 from your broker's website
2. Install and create a demo account
3. Enable DLL imports and automated trading

### Configure EA
1. **Copy ZMQ Library:**
   ```bash
   # Download ZMQ DLL for MT4
   # Copy zmq.dll to C:\Program Files\MetaTrader 4\MQL4\Libraries\
   ```

2. **Install EA:**
   - Copy `mt4/Experts/ZMQ_EA.mq4` to `C:\Program Files\MetaTrader 4\MQL4\Experts\`
   - Compile the EA in MetaEditor

3. **Configure EA Parameters:**
   - Open EA properties in MT4
   - Set `SERVER_IP` to your Oracle Cloud IP
   - Adjust risk parameters for demo trading:
     ```mq4
     RISK_PERCENT = 0.01  // 1% risk per trade for demo
     MAX_DAILY_LOSS = 0.02  // 2% max daily loss
     ```

4. **Attach to Chart:**
   - Open EURUSD chart (M1 timeframe)
   - Drag EA onto chart
   - Enable automated trading

## 5. Access Interfaces

### Streamlit Dashboard
- **URL:** `http://your-oracle-ip:8501`
- **Features:**
  - Real-time price charts
  - Account balance and P&L
  - Open trades monitoring
  - AI signal history
  - System health status

### Grafana Monitoring
- **URL:** `http://your-oracle-ip:3000`
- **Login:** admin / your_grafana_password
- **Dashboards:**
  - System performance metrics
  - AI model performance
  - Trade statistics
  - Latency monitoring

### Prometheus Metrics
- **URL:** `http://your-oracle-ip:9090`
- Raw metrics endpoint for monitoring

## 6. Initial Testing

### Demo Trading Phase
1. **Start with Demo Account:**
   ```mq4
   // In EA properties, set conservative parameters
   RISK_PERCENT = 0.005  // 0.5% risk per trade
   MAX_LOT_SIZE = 0.01   // Micro lots only
   ```

2. **Monitor Performance:**
   - Check dashboard for signal quality
   - Monitor latency (< 50ms target)
   - Review trade logs

3. **Validate Components:**
   ```bash
   # Test data ingestion
   docker-compose logs data_aggregator

   # Test AI pipeline
   docker-compose logs ai_backend

   # Test communication
   docker-compose logs zmq_bridge
   ```

### Minimum Demo Period
- Run for at least 1 week (5 trading days)
- Monitor win rate (>45% target)
- Check for system stability
- Validate risk management

## 7. Production Go-Live

### Pre-Production Checklist
- [ ] Demo account testing completed (1+ week)
- [ ] Win rate > 45%
- [ ] Average latency < 50ms
- [ ] No system crashes or errors
- [ ] Risk management validated
- [ ] Backup and recovery tested

### Switch to Live Account
1. **Update EA Parameters:**
   ```mq4
   RISK_PERCENT = 0.02  // 2% risk per trade
   MAX_DAILY_LOSS = 0.05  // 5% max daily loss
   ```

2. **Enable Live Trading:**
   - Switch MT4 to live account
   - Start with small position sizes
   - Monitor closely for first few days

## 8. Maintenance

### Daily Monitoring
- Check dashboard for system health
- Review trade performance
- Monitor latency and error logs

### Weekly Tasks
```bash
# Update AI models
docker-compose exec ai_backend python -m src.model_update

# Clean up old logs
docker-compose exec ai_backend find /app/logs -name "*.log" -mtime +7 -delete

# Database maintenance
docker-compose exec postgres vacuumdb -U trader -d trading_db --analyze
```

### Monthly Reviews
- Performance analysis
- Risk parameter adjustments
- System updates and patches

## Troubleshooting

### Common Issues

**MT4 Connection Failed:**
```bash
# Check Oracle Cloud security groups
# Verify SERVER_IP in EA matches Oracle IP
# Check MT4 logs for connection errors
```

**High Latency:**
```bash
# Check network connectivity
docker-compose logs zmq_bridge
# Verify Oracle Cloud region proximity to broker
```

**AI Signals Not Appearing:**
```bash
# Check data ingestion
docker-compose logs data_aggregator
# Verify API keys in .env
# Check AI model status
```

**Database Connection Issues:**
```bash
# Check PostgreSQL logs
docker-compose logs postgres
# Verify .env database credentials
# Check database disk space
```

### Logs and Debugging
```bash
# View all logs
docker-compose logs

# Follow specific service logs
docker-compose logs -f ai_backend

# Check MT4 logs in terminal
# C:\Program Files\MetaTrader 4\logs\
```

## Security Considerations

### Network Security
- Oracle Cloud security groups restrict access
- ZMQ communication uses private IPs
- API keys encrypted in environment variables

### Access Control
- SSH key authentication only
- Grafana admin password changed
- MT4 demo account for initial testing

### Data Protection
- Database backups scheduled
- Sensitive logs encrypted
- API keys rotated regularly

## Support

For issues and questions:
1. Check this documentation
2. Review logs: `docker-compose logs`
3. Check GitHub issues
4. Contact support with system diagnostics

---

**⚠️ Risk Warning:** This system involves high-risk trading. Always test thoroughly on demo accounts before live trading. Past performance does not guarantee future results.