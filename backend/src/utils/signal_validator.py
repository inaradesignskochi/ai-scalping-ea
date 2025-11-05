"""
Signal validation utility for AI trading signals
Ensures signals meet risk management and market condition criteria
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import numpy as np

from ..config import settings


class SignalValidator:
    """Validates AI trading signals before execution"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.recent_signals: List[Dict[str, Any]] = []
        self.max_signal_history = 100

    async def validate_signal(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Main signal validation function"""
        try:
            # Basic validation
            if not self._validate_basic_structure(signal):
                return False

            # Confidence threshold check
            if not self._validate_confidence(signal):
                return False

            # Market condition validation
            if not await self._validate_market_conditions(symbol, signal):
                return False

            # Risk management validation
            if not self._validate_risk_management(signal):
                return False

            # Frequency and correlation checks
            if not self._validate_signal_frequency(signal):
                return False

            # Volatility filter
            if not self._validate_volatility(symbol, signal):
                return False

            # Spread check
            if not self._validate_spread(symbol, signal):
                return False

            # Record validated signal
            self._record_signal(signal)

            self.logger.info(f"Signal validated: {signal['action']} {symbol} "
                           f"(confidence: {signal.get('confidence', 0):.2%})")
            return True

        except Exception as e:
            self.logger.error(f"Signal validation error: {e}")
            return False

    def _validate_basic_structure(self, signal: Dict[str, Any]) -> bool:
        """Validate basic signal structure"""
        required_fields = ['action', 'confidence']
        for field in required_fields:
            if field not in signal:
                self.logger.warning(f"Missing required field: {field}")
                return False

        if signal['action'] not in ['BUY', 'SELL', 'HOLD']:
            self.logger.warning(f"Invalid action: {signal['action']}")
            return False

        if not isinstance(signal['confidence'], (int, float)):
            self.logger.warning("Confidence must be numeric")
            return False

        return True

    def _validate_confidence(self, signal: Dict[str, Any]) -> bool:
        """Validate confidence threshold"""
        confidence = signal['confidence']

        if confidence < settings.confidence_threshold:
            self.logger.info(f"Signal rejected: confidence {confidence:.2%} below threshold "
                           f"{settings.confidence_threshold:.2%}")
            return False

        return True

    async def _validate_market_conditions(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Validate market conditions for signal"""
        # Check if market is open (simplified - in production check trading hours)
        current_hour = datetime.now().hour
        if not (0 <= current_hour <= 23):  # 24/7 for crypto, adjust for forex
            self.logger.info("Signal rejected: market closed")
            return False

        # Check for extreme market events (simplified)
        # In production, check for news events, economic data releases, etc.

        return True

    def _validate_risk_management(self, signal: Dict[str, Any]) -> bool:
        """Validate risk management parameters"""
        # Check position sizing (should be calculated by risk management)
        # This is a placeholder - actual validation happens in MT4 EA

        return True

    def _validate_signal_frequency(self, signal: Dict[str, Any]) -> bool:
        """Validate signal frequency to prevent overtrading"""
        # Check recent signals for same symbol
        recent_symbol_signals = [
            s for s in self.recent_signals[-20:]  # Last 20 signals
            if s.get('symbol') == signal.get('symbol')
        ]

        if len(recent_symbol_signals) >= 3:  # Max 3 signals per symbol in recent history
            self.logger.info("Signal rejected: too many recent signals for symbol")
            return False

        # Check for signal correlation (avoid conflicting signals)
        last_signal = next((s for s in reversed(self.recent_signals) if s.get('symbol') == signal.get('symbol')), None)
        if last_signal:
            time_diff = (datetime.now() - last_signal.get('timestamp', datetime.now())).seconds
            if time_diff < 60:  # Minimum 1 minute between signals
                self.logger.info("Signal rejected: too frequent signals")
                return False

        return True

    def _validate_volatility(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Validate volatility conditions"""
        # This is a placeholder - in production, check ATR, Bollinger Bands, etc.
        # Actual validation happens in MT4 EA with real market data

        # For scalping, we want some volatility but not extreme
        # This would be checked against recent ATR values

        return True

    def _validate_spread(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Validate spread conditions"""
        # This is a placeholder - actual spread checking happens in MT4 EA
        # Different symbols have different acceptable spread ranges

        return True

    def _record_signal(self, signal: Dict[str, Any]):
        """Record validated signal for frequency analysis"""
        signal_record = {
            'symbol': signal.get('symbol', 'UNKNOWN'),
            'action': signal['action'],
            'confidence': signal['confidence'],
            'timestamp': datetime.now()
        }

        self.recent_signals.append(signal_record)

        # Keep only recent history
        if len(self.recent_signals) > self.max_signal_history:
            self.recent_signals.pop(0)

    def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal statistics for monitoring"""
        if not self.recent_signals:
            return {'total_signals': 0, 'avg_confidence': 0.0}

        total_signals = len(self.recent_signals)
        avg_confidence = np.mean([s['confidence'] for s in self.recent_signals])

        # Signals by action
        actions = {}
        for signal in self.recent_signals:
            action = signal['action']
            actions[action] = actions.get(action, 0) + 1

        return {
            'total_signals': total_signals,
            'avg_confidence': avg_confidence,
            'actions': actions,
            'time_range': {
                'oldest': self.recent_signals[0]['timestamp'] if self.recent_signals else None,
                'newest': self.recent_signals[-1]['timestamp'] if self.recent_signals else None
            }
        }

    def reset_stats(self):
        """Reset signal statistics"""
        self.recent_signals.clear()
        self.logger.info("Signal statistics reset")


class MarketConditionValidator:
    """Advanced market condition validation"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def validate_liquidity(self, symbol: str) -> bool:
        """Validate market liquidity"""
        # Check order book depth, spread, volume
        # This would integrate with broker API or market data
        return True

    async def validate_news_impact(self, symbol: str) -> bool:
        """Check for news events that might affect trading"""
        # Check for scheduled news events, earnings, etc.
        # This would integrate with economic calendar APIs
        return True

    async def validate_correlation(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Check correlation with related assets"""
        # For EURUSD, check EUR and USD related assets
        # This helps avoid correlated signals that might cancel out
        return True