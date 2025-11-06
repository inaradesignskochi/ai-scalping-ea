# -*- coding: utf-8 -*-
"""
Test configuration and fixtures for AI Scalping EA
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime, timedelta
from typing import Dict, List, Any
import numpy as np

from src.config import Settings
from src.ai_orchestrator import AIOrchestrator, Agent
from src.data_ingestion import DataAggregator
from src.communication import ZMQBridge


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Mock(spec=Settings)
    settings.db_connection_string = "postgresql://test:test@localhost/test_db"
    settings.redis_connection_string = "redis://localhost:6379"
    settings.confidence_threshold = 0.75
    settings.model_update_interval = 3600
    settings.zmq_signal_port = 5555
    settings.zmq_heartbeat_port = 5556
    return settings


@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    base_time = datetime.utcnow()
    data = []
    
    for i in range(60):
        candle_time = base_time - timedelta(minutes=i)
        # Generate realistic EURUSD price movement
        base_price = 1.1000
        price_variation = np.sin(i * 0.1) * 0.005 + np.random.normal(0, 0.002)
        close_price = base_price + price_variation
        
        candle = {
            "time": candle_time.isoformat(),
            "open": close_price - 0.0005 + np.random.normal(0, 0.0001),
            "high": close_price + 0.001 + np.random.normal(0, 0.0002),
            "low": close_price - 0.001 - np.random.normal(0, 0.0002),
            "close": close_price,
            "volume": int(1000 + np.random.normal(0, 100)),
            "bid": close_price - 0.00005,
            "ask": close_price + 0.00005,
            "spread": 0.0001,
            "symbol": "EURUSD"
        }
        data.append(candle)
    
    return list(reversed(data))  # Chronological order


@pytest.fixture
def sample_news_data():
    """Sample news and sentiment data"""
    return [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "Reuters",
            "headline": "ECB maintains interest rates unchanged",
            "sentiment": 0.3,
            "relevance": 0.8,
            "url": "https://example.com/news1"
        },
        {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "Bloomberg",
            "headline": "EUR strengthens against USD",
            "sentiment": 0.5,
            "relevance": 0.9,
            "url": "https://example.com/news2"
        }
    ]


@pytest.fixture
def mock_agent():
    """Mock AI agent for testing"""
    agent = Mock(spec=Agent)
    agent.name = "test_agent"
    agent.model = AsyncMock()
    agent.performance_score = 0.6
    agent.version = "1.0.0"
    
    # Mock prediction
    agent.predict = AsyncMock(return_value={
        "agent": "test_agent",
        "action": "BUY",
        "confidence": 0.8,
        "reason": "Test prediction"
    })
    
    return agent


@pytest.fixture
def mock_ai_orchestrator(mock_settings, mock_agent):
    """Mock AI orchestrator for testing"""
    orchestrator = Mock(spec=AIOrchestrator)
    orchestrator.active_agents = {"test_agent": mock_agent}
    orchestrator.running = True
    
    # Mock methods
    orchestrator.start = AsyncMock()
    orchestrator.stop = AsyncMock()
    orchestrator.is_healthy = Mock(return_value=True)
    
    # Mock ensemble signal generation
    orchestrator.get_ensemble_signal = AsyncMock(return_value={
        "action": "BUY",
        "confidence": 0.85,
        "reason": "Ensemble consensus",
        "votes": {"BUY": 0.8, "SELL": 0.1, "HOLD": 0.1}
    })
    
    return orchestrator


@pytest.fixture
def mock_data_aggregator():
    """Mock data aggregator for testing"""
    aggregator = Mock(spec=DataAggregator)
    aggregator.running = True
    aggregator.start = AsyncMock()
    aggregator.stop = AsyncMock()
    aggregator.is_healthy = Mock(return_value=True)
    
    # Mock market data retrieval
    aggregator.get_recent_market_data = AsyncMock(return_value=[])
    aggregator.get_news_sentiment = AsyncMock(return_value=[])
    
    return aggregator


@pytest.fixture
def mock_zmq_bridge():
    """Mock ZMQ bridge for testing"""
    bridge = Mock(spec=ZMQBridge)
    bridge.running = True
    bridge.start = AsyncMock()
    bridge.stop = AsyncMock()
    bridge.is_healthy = Mock(return_value=True)
    
    # Mock signal sending
    bridge.send_signal = AsyncMock(return_value=True)
    bridge.send_heartbeat = AsyncMock(return_value=True)
    
    return bridge


@pytest.fixture
def performance_test_data():
    """Generate performance test data"""
    # Simulate 1000 trades
    np.random.seed(42)  # Reproducible results
    trades = []
    
    for i in range(1000):
        trade = {
            "trade_id": f"trade_{i}",
            "symbol": "EURUSD" if i % 2 == 0 else "GBPUSD",
            "action": "BUY" if i % 2 == 0 else "SELL",
            "entry_time": datetime.utcnow() - timedelta(hours=i),
            "exit_time": datetime.utcnow() - timedelta(hours=i-1),
            "pnl": np.random.normal(10, 5),  # Average $10, std dev $5
            "confidence": np.random.beta(2, 1),  # Skewed towards higher confidence
            "duration_minutes": np.random.exponential(30),  # Exponential distribution
            "lot_size": 0.1,
            "status": "closed"
        }
        trades.append(trade)
    
    return trades


@pytest.fixture
def security_test_data():
    """Test data for security testing"""
    return {
        "malicious_payload": {
            "symbol": "'; DROP TABLE trade_history; --",
            "action": "<script>alert('xss')</script>",
            "confidence": "'; DELETE FROM model_registry; --"
        },
        "injection_attempt": {
            "symbol": "EURUSD' OR '1'='1",
            "action": "BUY'; WAITFOR DELAY '00:00:05'--"
        },
        "buffer_overflow": {
            "symbol": "A" * 10000,
            "action": "B" * 10000,
            "confidence": 0.99
        }
    }


@pytest.fixture
def load_test_scenarios():
    """Load testing scenarios"""
    return [
        {"concurrency": 100, "duration": 60},  # 100 users for 1 minute
        {"concurrency": 500, "duration": 120},  # 500 users for 2 minutes
        {"concurrency": 1000, "duration": 300},  # 1000 users for 5 minutes
    ]


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically setup test environment"""
    # Set test environment variables
    import os
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DEBUG"] = "true"
    os.environ["LOG_LEVEL"] = "debug"
    
    yield
    
    # Cleanup
    if "ENVIRONMENT" in os.environ:
        del os.environ["ENVIRONMENT"]


@pytest.fixture
def latency_tracker():
    """Track latency for performance testing"""
    class LatencyTracker:
        def __init__(self):
            self.measurements = []
        
        def measure(self, func, *args, **kwargs):
            import time
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            latency = (end - start) * 1000  # Convert to milliseconds
            self.measurements.append(latency)
            return result, latency
        
        def get_stats(self):
            if not self.measurements:
                return {}
            
            return {
                "count": len(self.measurements),
                "min": min(self.measurements),
                "max": max(self.measurements),
                "avg": sum(self.measurements) / len(self.measurements),
                "p95": np.percentile(self.measurements, 95),
                "p99": np.percentile(self.measurements, 99)
            }
        
        def assert_performance(self, max_latency_ms=5):
            """Assert that all measurements are below threshold"""
            stats = self.get_stats()
            assert stats["p99"] < max_latency_ms, f"99th percentile latency {stats['p99']:.2f}ms exceeds {max_latency_ms}ms"
    
    return LatencyTracker()


# Custom markers for test categorization
def pytest_configure(config):
    """Configure custom test markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "latency: mark test that measures latency"
    )