# 🚀 Enhanced AI-Driven Scalping EA

A production-ready, ultra-low latency AI-powered scalping Expert Advisor for MetaTrader 4, featuring multi-agent ensemble AI, ZeroMQ communication, and comprehensive monitoring.

## 🏗️ Architecture Overview

This system implements a 5-layer architecture:
- **Layer 1:** Multi-source data ingestion (MT4 ticks, crypto WebSockets, news APIs, social sentiment)
- **Layer 2:** AI processing pipeline with hot-swappable multi-agent ensemble
- **Layer 3:** Ultra-low latency communication bridge (ZeroMQ primary + WebSocket fallback)
- **Layer 4:** Smart MT4 Expert Advisor with advanced risk management
- **Layer 5:** Real-time monitoring and analytics (Streamlit + Grafana)

## 🚀 Quick Start

### Prerequisites
- Oracle Cloud Always Free account (Ampere A1 instance)
- MetaTrader 4 terminal
- GitHub account

### 1. Oracle Cloud Setup
```bash
# Create Ubuntu 22.04 instance
# Configure security lists: 22, 80, 443, 5555, 5556, 8501, 3000, 9090
```

### 2. Deploy to Oracle Cloud
```bash
git clone https://github.com/yourusername/ai-scalping-ea.git
cd ai-scalping-ea
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d --build
```

### 3. MT4 Setup
- Copy `zmq.dll` to `MT4/MQL4/Libraries/`
- Compile `ZMQ_EA.mq4` in MetaEditor
- Set `SERVER_IP` to your Oracle Cloud public IP
- Enable AutoTrading and DLL imports

### 4. Access Interfaces
- **Dashboard:** http://your-ip:8501
- **Grafana:** http://your-ip:3000 (admin/admin)
- **Prometheus:** http://your-ip:9090

## 📊 Key Features

- **Ultra-Low Latency:** <10ms end-to-end using ZeroMQ
- **Multi-Agent AI:** Ensemble of 4 specialized agents with hot-swapping
- **Advanced Risk Management:** Kelly Criterion, multi-level TP/SL, circuit breakers
- **Production Monitoring:** Real-time dashboards and alerting
- **Zero-Downtime Deployment:** Rolling updates with automatic rollback
- **Free Infrastructure:** Optimized for Oracle Cloud Always Free tier

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Database
DB_PASSWORD=your_secure_password
POSTGRES_DB=trading_db
POSTGRES_USER=trader

# AI APIs
GEMINI_API_KEY=your_gemini_key

# Monitoring
GRAFANA_PASSWORD=your_grafana_password

# MT4 Connection
MT4_SERVER_IP=your_mt4_server_ip
MT4_LOGIN=your_login
MT4_PASSWORD=your_password

# API Keys (Free Tiers)
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
MARKETAUX_API_KEY=your_marketaux_key
```

## 🧪 Testing

```bash
# Run unit tests
pytest tests/ --cov=./

# Backtest models
python backtest_runner.py --start 2024-01-01 --end 2024-11-01

# Integration tests
python test_integration.py
```

## 📈 Performance Metrics

- **Latency:** <10ms end-to-end
- **Signal Quality:** 75%+ confidence threshold
- **Win Rate:** Target 55-65% with proper risk management
- **Max Drawdown:** <5% with circuit breakers

## ⚠️ Risk Warnings

- **High Risk:** Scalping requires extreme precision and fast execution
- **Demo First:** Always test on demo account for minimum 1 month
- **Capital Requirements:** Start with minimum $1000
- **Broker Selection:** Use ECN brokers with tight spreads (<2 pips)
- **Latency Critical:** Ensure <50ms between Oracle Cloud and broker

## 📚 Documentation

- [Setup Guide](docs/setup.md)
- [API Reference](docs/api.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Architecture Details](docs/architecture.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚡ Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting guide
- Join our Discord community

---

**Disclaimer:** This software is for educational and research purposes. Trading involves substantial risk of loss. Past performance does not guarantee future results. Use at your own risk.