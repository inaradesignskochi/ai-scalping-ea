# -*- coding: utf-8 -*-
"""
Comprehensive tests for AI Orchestrator
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from src.ai_orchestrator import AIOrchestrator, Agent
from src.utils.signal_validator import SignalValidator


class TestAgent:
    """Test cases for Agent class"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization"""
        agent = Agent("technical", "/models/technical.pkl", "1.0.0", 0.6)
        
        assert agent.name == "technical"
        assert agent.model_path == "/models/technical.pkl"
        assert agent.version == "1.0.0"
        assert agent.performance_score == 0.6
        assert agent.model is None
        assert agent.last_updated is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_load_model(self, mock_agent):
        """Test agent model loading"""
        # Mock the model loader
        with patch('src.ai_orchestrator.ModelLoader') as mock_loader:
            mock_model = AsyncMock()
            mock_loader.load_model.return_value = mock_model
            
            await mock_agent.load_model()
            mock_loader.load_model.assert_called_once_with(mock_agent.model_path)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_prediction_flow(self, mock_agent):
        """Test complete prediction flow"""
        # Setup mock data
        test_data = {
            "symbol": "EURUSD",
            "market_data": [{"close": 1.1000, "high": 1.1010, "low": 1.0990, "volume": 1000}] * 60,
            "news_data": [{"sentiment": 0.5, "relevance": 0.8}]
        }
        
        # Execute prediction
        result = await mock_agent.predict(test_data)
        
        # Verify result structure
        assert "agent" in result
        assert "action" in result
        assert "confidence" in result
        assert "reason" in result
        assert result["agent"] == "test_agent"
        
        # Verify mock was called
        mock_agent.predict.assert_called_once_with(test_data)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_prediction_error_handling(self):
        """Test error handling in predictions"""
        agent = Agent("error_agent", "/models/error.pkl", "1.0.0", 0.5)
        agent.model = AsyncMock()
        agent.model.predict.side_effect = Exception("Model error")
        
        test_data = {"symbol": "EURUSD", "market_data": [], "news_data": []}
        
        result = await agent.predict(test_data)
        
        # Should return safe default on error
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0
        assert "Error:" in result["reason"]
    
    @pytest.mark.unit
    def test_technical_indicators(self):
        """Test technical indicator calculations"""
        agent = Agent("technical", "/models/technical.pkl", "1.0.0", 0.6)
        
        # Test RSI calculation
        prices = [1.1000, 1.1010, 1.1020, 1.1015, 1.1025, 1.1030]
        rsi = agent._calculate_rsi(prices)
        assert 0 <= rsi <= 100
        
        # Test MACD calculation
        prices = [1.1000 + i * 0.001 for i in range(30)]
        macd_result = agent._calculate_macd(prices)
        assert len(macd_result) == 3  # macd, signal, histogram
        
        # Test Bollinger Bands
        bb_result = agent._calculate_bollinger_bands(prices)
        assert len(bb_result) == 3  # sma, upper, lower
    
    @pytest.mark.unit
    def test_atr_calculation(self):
        """Test ATR calculation"""
        agent = Agent("risk", "/models/risk.pkl", "1.0.0", 0.6)
        
        market_data = [
            {"high": 1.1010, "low": 1.0990, "close": 1.1005},
            {"high": 1.1015, "low": 1.1000, "close": 1.1010},
            {"high": 1.1020, "low": 1.1005, "close": 1.1015}
        ]
        
        atr = agent._calculate_atr(market_data)
        assert atr >= 0


class TestAIOrchestrator:
    """Test cases for AIOrchestrator class"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, mock_settings):
        """Test orchestrator initialization"""
        with patch('src.ai_orchestrator.psycopg2.connect'):
            orchestrator = AIOrchestrator()
            assert orchestrator.active_agents == {}
            assert orchestrator.performance_metrics == {}
            assert orchestrator.running is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_orchestrator_startup_and_shutdown(self, mock_ai_orchestrator):
        """Test startup and shutdown sequence"""
        await mock_ai_orchestrator.start()
        mock_ai_orchestrator.start.assert_called_once()
        
        await mock_ai_orchestrator.stop()
        mock_ai_orchestrator.stop.assert_called_once()
        assert mock_ai_orchestrator.running is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check(self, mock_ai_orchestrator):
        """Test health check functionality"""
        # Test healthy state
        mock_ai_orchestrator.running = True
        mock_ai_orchestrator.active_agents = {"agent1": Mock(), "agent2": Mock()}
        assert mock_ai_orchestrator.is_healthy() is True
        
        # Test unhealthy states
        mock_ai_orchestrator.running = False
        assert mock_ai_orchestrator.is_healthy() is False
        
        mock_ai_orchestrator.running = True
        mock_ai_orchestrator.active_agents = {}
        assert mock_ai_orchestrator.is_healthy() is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ensemble_signal_generation(self, mock_ai_orchestrator, sample_market_data):
        """Test ensemble signal generation"""
        result = await mock_ai_orchestrator.get_ensemble_signal(
            "EURUSD", sample_market_data, []
        )
        
        # Verify signal structure
        assert "action" in result
        assert "confidence" in result
        assert "reason" in result
        assert "votes" in result
        assert result["action"] in ["BUY", "SELL", "HOLD"]
        assert 0 <= result["confidence"] <= 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_confidence_threshold_filtering(self, mock_ai_orchestrator):
        """Test confidence threshold filtering"""
        # Mock low confidence result
        mock_ai_orchestrator.get_ensemble_signal = AsyncMock(return_value={
            "action": "BUY",
            "confidence": 0.3,  # Below threshold
            "reason": "Low confidence"
        })
        
        with patch('src.ai_orchestrator.settings') as mock_settings:
            mock_settings.confidence_threshold = 0.75
            
            result = await mock_ai_orchestrator.get_ensemble_signal(
                "EURUSD", [], []
            )
            
            # Should be filtered to HOLD due to low confidence
            assert result["action"] == "HOLD"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_weighted_voting(self, mock_ai_orchestrator):
        """Test weighted voting mechanism"""
        # Create test agent results
        agent_results = [
            {"agent": "agent1", "action": "BUY", "confidence": 0.8, "reason": "Technical bullish"},
            {"agent": "agent2", "action": "SELL", "confidence": 0.6, "reason": "Sentiment bearish"},
            {"agent": "agent3", "action": "BUY", "confidence": 0.7, "reason": "Price momentum"}
        ]
        
        # Set different performance scores
        mock_ai_orchestrator.active_agents = {
            "agent1": Mock(performance_score=0.8),
            "agent2": Mock(performance_score=0.5),
            "agent3": Mock(performance_score=0.7)
        }
        
        result = await mock_ai_orchestrator._weighted_vote(agent_results)
        
        # Verify voting mechanism
        assert "action" in result
        assert "confidence" in result
        assert "votes" in result
        assert sum(result["votes"].values()) <= 1.0  # Normalized
        
        # Higher confidence agents should have more influence
        assert result["votes"]["BUY"] > result["votes"]["SELL"]
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_signal_processing_latency(self, mock_ai_orchestrator, latency_tracker, sample_market_data):
        """Test signal processing latency requirements"""
        # Test multiple iterations to get latency distribution
        for _ in range(100):
            def generate_signal():
                return asyncio.run(mock_ai_orchestrator.get_ensemble_signal(
                    "EURUSD", sample_market_data, []
                ))
            
            _, latency = latency_tracker.measure(generate_signal)
        
        stats = latency_tracker.get_stats()
        
        # Performance assertions
        assert stats["count"] == 100
        assert stats["avg"] < 5.0, f"Average latency {stats['avg']:.2f}ms exceeds 5ms"
        assert stats["p95"] < 10.0, f"95th percentile latency {stats['p95']:.2f}ms exceeds 10ms"
        assert stats["p99"] < 20.0, f"99th percentile latency {stats['p99']:.2f}ms exceeds 20ms"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_signal_processing(self, mock_ai_orchestrator, sample_market_data):
        """Test concurrent signal processing"""
        # Generate multiple concurrent requests
        tasks = [
            mock_ai_orchestrator.get_ensemble_signal("EURUSD", sample_market_data, [])
            for _ in range(50)
        ]
        
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        total_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Verify all requests completed
        assert len(results) == 50
        
        # Verify reasonable processing time (parallelism benefit)
        assert total_time < 250, f"Concurrent processing took {total_time:.2f}ms, expected <250ms"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_performance_monitoring(self, mock_ai_orchestrator):
        """Test performance monitoring functionality"""
        # Mock database connection
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"agent_name": "technical", "win_rate": 0.65, "avg_pnl": 15.5, "trade_count": 20}
        ]
        mock_ai_orchestrator.db_conn = mock_db
        
        # Test performance update
        await mock_ai_orchestrator._update_performance_scores()
        
        # Verify database operations
        mock_cursor.execute.assert_called()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_model_hotswap_mechanism(self, mock_ai_orchestrator):
        """Test automatic model hot-swapping"""
        # Mock underperforming model
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"agent_name": "technical", "performance_score": 0.35, "version": "1.0.0"}
        ]
        mock_cursor.fetchone.return_value = {
            "model_path": "/models/technical_v2.pkl",
            "version": "2.0.0",
            "performance_score": 0.65
        }
        mock_ai_orchestrator.db_conn = mock_db
        
        # Test model swap
        await mock_ai_orchestrator._check_model_performance()
        
        # Verify swap operations
        assert mock_cursor.execute.call_count >= 2  # Check and swap operations
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_signal_validation_integration(self, mock_ai_orchestrator, sample_market_data):
        """Test signal validation integration"""
        # Mock validator to reject signal
        with patch.object(SignalValidator, 'validate_signal', return_value=False):
            result = await mock_ai_orchestrator.get_ensemble_signal(
                "EURUSD", sample_market_data, []
            )
            
            # Should be filtered to HOLD due to validation failure
            assert result["action"] == "HOLD"
            assert "validation" in result["reason"].lower()
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_malicious_data_handling(self, mock_ai_orchestrator):
        """Test handling of malicious data inputs"""
        malicious_data = {
            "symbol": "'; DROP TABLE trade_history; --",
            "market_data": [{"close": "<script>alert('xss')</script>"}] * 60,
            "news_data": [{"sentiment": "'; DELETE FROM model_registry; --"}]
        }
        
        # Should handle gracefully without crashing
        try:
            result = await mock_ai_orchestrator.get_ensemble_signal(
                malicious_data["symbol"],
                malicious_data["market_data"],
                malicious_data["news_data"]
            )
            
            # Should return safe default response
            assert result["action"] in ["BUY", "SELL", "HOLD"]
            assert "Error:" not in result["reason"]  # No error messages leaked
            
        except Exception as e:
            # Should not raise unhandled exceptions
            pytest.fail(f"Unhandled exception: {e}")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_edge_cases(self, mock_ai_orchestrator):
        """Test edge cases and boundary conditions"""
        # Test with empty data
        result = await mock_ai_orchestrator.get_ensemble_signal("EURUSD", [], [])
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0
        
        # Test with None data
        mock_ai_orchestrator.active_agents = {}
        result = await mock_ai_orchestrator.get_ensemble_signal("EURUSD", None, None)
        assert result["action"] == "HOLD"
        assert "No active agents" in result["reason"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_signal_pipeline(mock_ai_orchestrator, sample_market_data, sample_news_data):
    """End-to-end test of the signal generation pipeline"""
    # Start orchestrator
    await mock_ai_orchestrator.start()
    
    try:
        # Generate signal through full pipeline
        signal = await mock_ai_orchestrator.get_ensemble_signal(
            "EURUSD", sample_market_data, sample_news_data
        )
        
        # Verify complete signal structure
        assert signal["action"] in ["BUY", "SELL", "HOLD"]
        assert 0 <= signal["confidence"] <= 1
        assert len(signal["reason"]) > 0
        assert all(k in signal["votes"] for k in ["BUY", "SELL", "HOLD"])
        
        # Verify health status
        assert mock_ai_orchestrator.is_healthy() is True
        
    finally:
        await mock_ai_orchestrator.stop()