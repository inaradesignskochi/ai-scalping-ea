"""
AI Orchestrator - Multi-agent ensemble with hot-swapping
Manages AI model loading, performance tracking, and signal generation
"""

import asyncio
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

from .config import settings
from .utils.model_loader import ModelLoader
from .utils.signal_validator import SignalValidator


class Agent:
    """Individual AI agent wrapper"""

    def __init__(self, name: str, model_path: str, version: str, performance_score: float):
        self.name = name
        self.model_path = model_path
        self.version = version
        self.performance_score = performance_score
        self.model = None
        self.last_updated = datetime.now()
        self.logger = logging.getLogger(f"{__name__}.{name}")

    async def load_model(self):
        """Load model asynchronously"""
        try:
            self.model = await ModelLoader.load_model(self.model_path)
            self.logger.info(f"Loaded model {self.name} v{self.version}")
        except Exception as e:
            self.logger.error(f"Failed to load model {self.name}: {e}")
            raise

    async def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate prediction"""
        if not self.model:
            await self.load_model()

        try:
            # Preprocess data based on agent type
            processed_data = await self._preprocess_data(data)

            # Generate prediction
            prediction = await self.model.predict(processed_data)

            # Post-process result
            result = await self._postprocess_prediction(prediction)

            return {
                "agent": self.name,
                "action": result["action"],
                "confidence": float(result["confidence"]),
                "reason": result.get("reason", ""),
                "metadata": result.get("metadata", {})
            }

        except Exception as e:
            self.logger.error(f"Prediction failed for {self.name}: {e}")
            return {
                "agent": self.name,
                "action": "HOLD",
                "confidence": 0.0,
                "reason": f"Error: {str(e)}",
                "metadata": {}
            }

    async def _preprocess_data(self, data: Dict[str, Any]) -> np.ndarray:
        """Preprocess input data for the model"""
        if self.name == "technical":
            return await self._preprocess_technical_data(data)
        elif self.name == "sentiment":
            return await self._preprocess_sentiment_data(data)
        elif self.name == "price_prediction":
            return await self._preprocess_price_data(data)
        elif self.name == "risk_assessment":
            return await self._preprocess_risk_data(data)
        else:
            return np.array([])

    async def _preprocess_technical_data(self, data: Dict[str, Any]) -> np.ndarray:
        """Preprocess technical analysis data"""
        # Extract OHLCV and technical indicators
        features = []
        market_data = data.get("market_data", [])

        if len(market_data) >= 60:  # Need at least 60 candles
            recent_data = market_data[-60:]

            # Basic OHLCV
            closes = [candle.get("close", candle.get("price", 0)) for candle in recent_data]
            highs = [candle.get("high", 0) for candle in recent_data]
            lows = [candle.get("low", 0) for candle in recent_data]
            volumes = [candle.get("volume", 0) for candle in recent_data]

            # Calculate technical indicators
            features.extend(closes)
            features.extend(highs)
            features.extend(lows)
            features.extend(volumes)

            # RSI (simplified)
            rsi = self._calculate_rsi(closes)
            features.append(rsi)

            # MACD (simplified)
            macd = self._calculate_macd(closes)
            features.extend(macd)

            # Bollinger Bands (simplified)
            bb = self._calculate_bollinger_bands(closes)
            features.extend(bb)

        return np.array(features).reshape(1, -1)

    async def _preprocess_sentiment_data(self, data: Dict[str, Any]) -> np.ndarray:
        """Preprocess sentiment data"""
        news_data = data.get("news_data", [])

        if news_data:
            # Simple sentiment aggregation
            sentiments = [item.get("sentiment", 0.0) for item in news_data[-10:]]  # Last 10 news items
            avg_sentiment = np.mean(sentiments) if sentiments else 0.0

            # Create feature vector
            features = [avg_sentiment, len(sentiments), np.std(sentiments) if sentiments else 0.0]
        else:
            features = [0.0, 0, 0.0]

        return np.array(features).reshape(1, -1)

    async def _preprocess_price_data(self, data: Dict[str, Any]) -> np.ndarray:
        """Preprocess price prediction data"""
        market_data = data.get("market_data", [])

        if len(market_data) >= 20:
            closes = [candle.get("close", candle.get("price", 0)) for candle in market_data[-20:]]
            features = closes
        else:
            features = [0.0] * 20

        return np.array(features).reshape(1, -1)

    async def _preprocess_risk_data(self, data: Dict[str, Any]) -> np.ndarray:
        """Preprocess risk assessment data"""
        market_data = data.get("market_data", [])

        if market_data:
            latest = market_data[-1]
            price = latest.get("close", latest.get("price", 0))
            volume = latest.get("volume", 0)
            spread = latest.get("spread", 2.0)  # Default spread

            # Calculate ATR (simplified)
            atr = self._calculate_atr(market_data)

            # Time of day factor
            hour = datetime.now().hour
            time_factor = 1.0 if 8 <= hour <= 16 else 0.5  # Trading hours

            features = [price, volume, spread, atr, time_factor]
        else:
            features = [0.0, 0.0, 2.0, 0.0, 0.5]

        return np.array(features).reshape(1, -1)

    async def _postprocess_prediction(self, prediction: Any) -> Dict[str, Any]:
        """Post-process model prediction"""
        if isinstance(prediction, np.ndarray):
            if len(prediction.shape) > 1:
                prediction = prediction.flatten()

            # Assume first element is decision, second is confidence
            if len(prediction) >= 2:
                decision_value = prediction[0]
                confidence = float(prediction[1])
            else:
                decision_value = prediction[0]
                confidence = 0.5

            # Convert decision to action
            if decision_value > 0.6:
                action = "BUY"
            elif decision_value < 0.4:
                action = "SELL"
            else:
                action = "HOLD"

        elif isinstance(prediction, dict):
            action = prediction.get("action", "HOLD")
            confidence = prediction.get("confidence", 0.5)
        else:
            action = "HOLD"
            confidence = 0.0

        return {
            "action": action,
            "confidence": confidence,
            "reason": f"Model prediction: {action} with {confidence:.2%} confidence",
            "metadata": {"raw_prediction": str(prediction)}
        }

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self, prices: List[float]) -> List[float]:
        """Calculate MACD (simplified)"""
        if len(prices) < 26:
            return [0.0, 0.0, 0.0]

        ema12 = np.mean(prices[-12:])
        ema26 = np.mean(prices[-26:])
        macd = ema12 - ema26
        signal = np.mean([macd])  # Simplified signal line
        histogram = macd - signal

        return [macd, signal, histogram]

    def _calculate_bollinger_bands(self, prices: List[float]) -> List[float]:
        """Calculate Bollinger Bands (simplified)"""
        if len(prices) < 20:
            return [0.0, 0.0, 0.0]

        sma = np.mean(prices[-20:])
        std = np.std(prices[-20:])

        upper = sma + (2 * std)
        lower = sma - (2 * std)

        return [sma, upper, lower]

    def _calculate_atr(self, market_data: List[Dict[str, Any]], period: int = 14) -> float:
        """Calculate ATR"""
        if len(market_data) < period:
            return 0.0

        tr_values = []
        for i in range(1, min(len(market_data), period + 1)):
            high = market_data[i].get("high", 0)
            low = market_data[i].get("low", 0)
            prev_close = market_data[i-1].get("close", market_data[i-1].get("price", 0))

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        return np.mean(tr_values) if tr_values else 0.0


class AIOrchestrator:
    """Main AI orchestration system"""

    def __init__(self):
        self.db_conn = None
        self.model_registry = {}
        self.active_agents = {}
        self.performance_metrics = {}
        self.signal_validator = SignalValidator()
        self.logger = logging.getLogger(__name__)
        self.running = False

    async def start(self):
        """Start AI orchestration"""
        self.running = True
        self.logger.info("Starting AI Orchestrator...")

        # Connect to database
        try:
            self.db_conn = psycopg2.connect(settings.db_connection_string)
            self.logger.info("Connected to database")
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise

        # Load active models
        await self.load_active_models()

        # Start background tasks
        asyncio.create_task(self._performance_monitoring_loop())
        asyncio.create_task(self._model_hotswap_loop())

    async def stop(self):
        """Stop AI orchestration"""
        self.running = False
        if self.db_conn:
            self.db_conn.close()
        self.logger.info("AI Orchestrator stopped")

    async def load_active_models(self):
        """Load models marked as active in database"""
        try:
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT agent_name, model_path, version, performance_score
                    FROM model_registry
                    WHERE status = 'active'
                    ORDER BY performance_score DESC
                """)

                for row in cursor.fetchall():
                    agent = Agent(
                        row['agent_name'],
                        row['model_path'],
                        row['version'],
                        row['performance_score']
                    )

                    # Load model
                    await agent.load_model()
                    self.active_agents[agent.name] = agent
                    self.logger.info(f"Loaded active agent: {agent.name} v{agent.version}")

        except Exception as e:
            self.logger.error(f"Failed to load active models: {e}")

    async def get_ensemble_signal(self, symbol: str, market_data: List[Dict[str, Any]],
                                news_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get aggregated signal from all active agents"""
        if not self.active_agents:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": "No active agents available",
                "votes": {"BUY": 0, "SELL": 0, "HOLD": 0}
            }

        # Prepare data for agents
        data = {
            "symbol": symbol,
            "market_data": market_data,
            "news_data": news_data or []
        }

        # Run all agents in parallel
        tasks = [agent.predict(data) for agent in self.active_agents.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        valid_results = []
        for result in results:
            if isinstance(result, dict) and "action" in result:
                valid_results.append(result)

        if not valid_results:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": "No valid agent predictions",
                "votes": {"BUY": 0, "SELL": 0, "HOLD": 0}
            }

        # Weighted voting based on performance
        ensemble_result = await self._weighted_vote(valid_results)

        # Check confidence threshold
        if ensemble_result['confidence'] < settings.confidence_threshold:
            ensemble_result['action'] = 'HOLD'
            ensemble_result['reason'] += f" | Confidence below threshold ({settings.confidence_threshold})"

        # Additional validation
        if not await self.signal_validator.validate_signal(symbol, ensemble_result):
            ensemble_result['action'] = 'HOLD'
            ensemble_result['reason'] += " | Failed signal validation"

        # Log signal for performance tracking
        await self._log_signal(symbol, ensemble_result, valid_results)

        return ensemble_result

    async def _weighted_vote(self, agent_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate signals using performance-weighted voting"""
        votes = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        total_weight = 0.0
        reasons = []
        confidences = []

        for result in agent_results:
            agent_name = result['agent']
            agent = self.active_agents.get(agent_name)

            if agent:
                weight = agent.performance_score
                action = result['action']
                confidence = result['confidence']

                votes[action] += weight * confidence
                total_weight += weight
                reasons.append(f"{agent_name}: {result['reason']}")
                confidences.append(confidence)

        # Normalize votes
        if total_weight > 0:
            for action in votes:
                votes[action] /= total_weight

        # Determine winning action
        winning_action = max(votes, key=votes.get)
        final_confidence = np.mean(confidences) if confidences else 0.0

        return {
            "action": winning_action,
            "confidence": final_confidence,
            "reason": " | ".join(reasons),
            "votes": votes
        }

    async def _log_signal(self, symbol: str, ensemble_result: Dict[str, Any],
                         agent_results: List[Dict[str, Any]]):
        """Log signal for performance tracking"""
        try:
            signal_data = {
                "symbol": symbol,
                "timestamp": datetime.now(),
                "ensemble_action": ensemble_result["action"],
                "ensemble_confidence": ensemble_result["confidence"],
                "agent_signals": agent_results,
                "votes": ensemble_result["votes"]
            }

            with self.db_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ai_performance (timestamp, agent_name, metric_name, metric_value, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    signal_data["timestamp"],
                    "ensemble",
                    "signal_confidence",
                    signal_data["ensemble_confidence"],
                    json.dumps(signal_data)
                ))

            self.db_conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to log signal: {e}")

    async def _performance_monitoring_loop(self):
        """Monitor agent performance and update scores"""
        while self.running:
            try:
                await self._update_performance_scores()
                await asyncio.sleep(settings.model_update_interval)

            except Exception as e:
                self.logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(60)

    async def _update_performance_scores(self):
        """Update performance scores based on recent trade results"""
        try:
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Calculate performance over last 24 hours
                cursor.execute("""
                    SELECT
                        agent_name,
                        AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
                        AVG(pnl) as avg_pnl,
                        COUNT(*) as trade_count
                    FROM trade_history
                    WHERE entry_time > NOW() - INTERVAL '24 hours'
                    AND agent_name IS NOT NULL
                    GROUP BY agent_name
                """)

                performance_data = cursor.fetchall()

                for row in performance_data:
                    agent_name = row['agent_name']
                    win_rate = row['win_rate'] or 0.0
                    avg_pnl = row['avg_pnl'] or 0.0
                    trade_count = row['trade_count'] or 0

                    # Calculate composite score (weighted combination)
                    if trade_count >= 10:  # Minimum trades for reliable stats
                        performance_score = (win_rate * 0.7) + (min(avg_pnl / 100, 1.0) * 0.3)
                        performance_score = max(0.0, min(1.0, performance_score))

                        # Update in database
                        cursor.execute("""
                            UPDATE model_registry
                            SET performance_score = %s, updated_at = NOW()
                            WHERE agent_name = %s
                        """, (performance_score, agent_name))

                        # Update in-memory agent
                        if agent_name in self.active_agents:
                            self.active_agents[agent_name].performance_score = performance_score

                        self.logger.info(f"Updated {agent_name} performance score: {performance_score:.3f}")

                self.db_conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to update performance scores: {e}")

    async def _model_hotswap_loop(self):
        """Check for model performance and trigger hot-swaps"""
        while self.running:
            try:
                await self._check_model_performance()
                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.error(f"Model hot-swap error: {e}")
                await asyncio.sleep(60)

    async def _check_model_performance(self):
        """Check if any models need to be swapped due to poor performance"""
        try:
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Find underperforming models
                cursor.execute("""
                    SELECT agent_name, performance_score, version
                    FROM model_registry
                    WHERE status = 'active'
                    AND performance_score < 0.45  -- Below 45% performance
                    AND updated_at > NOW() - INTERVAL '1 hour'
                """)

                underperformers = cursor.fetchall()

                for row in underperformers:
                    agent_name = row['agent_name']
                    current_score = row['performance_score']

                    # Look for backup models
                    cursor.execute("""
                        SELECT model_path, version, performance_score
                        FROM model_registry
                        WHERE agent_name = %s
                        AND status = 'inactive'
                        AND performance_score > %s
                        ORDER BY performance_score DESC
                        LIMIT 1
                    """, (agent_name, current_score))

                    backup = cursor.fetchone()

                    if backup:
                        await self._swap_model(agent_name, backup)
                        self.logger.warning(f"Hot-swapped {agent_name} due to poor performance ({current_score:.3f})")

        except Exception as e:
            self.logger.error(f"Model performance check failed: {e}")

    async def _swap_model(self, agent_name: str, backup_model: Dict[str, Any]):
        """Swap to backup model"""
        try:
            # Update database
            with self.db_conn.cursor() as cursor:
                # Deactivate current model
                cursor.execute("""
                    UPDATE model_registry
                    SET status = 'inactive'
                    WHERE agent_name = %s AND status = 'active'
                """, (agent_name,))

                # Activate backup model
                cursor.execute("""
                    UPDATE model_registry
                    SET status = 'active'
                    WHERE agent_name = %s AND version = %s
                """, (agent_name, backup_model['version']))

                self.db_conn.commit()

            # Load new model in memory
            new_agent = Agent(
                agent_name,
                backup_model['model_path'],
                backup_model['version'],
                backup_model['performance_score']
            )

            await new_agent.load_model()
            self.active_agents[agent_name] = new_agent

            self.logger.info(f"Successfully swapped {agent_name} to v{backup_model['version']}")

        except Exception as e:
            self.logger.error(f"Model swap failed for {agent_name}: {e}")

    def is_healthy(self) -> bool:
        """Health check"""
        return self.running and len(self.active_agents) > 0