"""
Message serialization utilities for communication bridges
Handles conversion between different message formats (JSON, Protobuf, etc.)
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Union
import google.protobuf.json_format as json_format

from ..config import settings


class MessageSerializer:
    """Unified message serializer for different protocols"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def serialize_signal(self, signal: Dict[str, Any]) -> bytes:
        """Serialize trading signal for ZMQ transmission"""
        try:
            # Prepare signal data
            signal_data = {
                "type": "signal",
                "symbol": signal.get("symbol", ""),
                "action": signal.get("action", "HOLD"),
                "confidence": float(signal.get("confidence", 0.0)),
                "reason": signal.get("reason", ""),
                "server_timestamp": signal.get("server_timestamp", 0),
                "votes": signal.get("votes", {}),
                "metadata": signal.get("metadata", {})
            }

            # Convert to JSON string
            json_str = json.dumps(signal_data, default=self._json_serializer)

            # Return as bytes for ZMQ
            return json_str.encode('utf-8')

        except Exception as e:
            self.logger.error(f"Failed to serialize signal: {e}")
            return b'{"type": "error", "message": "Serialization failed"}'

    def deserialize_signal(self, data: bytes) -> Dict[str, Any]:
        """Deserialize trading signal from ZMQ"""
        try:
            json_str = data.decode('utf-8')
            signal_data = json.loads(json_str)

            # Validate required fields
            if signal_data.get("type") != "signal":
                raise ValueError("Invalid signal type")

            return signal_data

        except Exception as e:
            self.logger.error(f"Failed to deserialize signal: {e}")
            return {"type": "error", "message": "Deserialization failed"}

    def serialize_heartbeat(self, heartbeat: Dict[str, Any]) -> bytes:
        """Serialize heartbeat response for ZMQ"""
        try:
            heartbeat_data = {
                "type": "heartbeat_response",
                "status": heartbeat.get("status", "unknown"),
                "server_time": heartbeat.get("server_time", 0),
                "avg_latency_ms": heartbeat.get("avg_latency_ms", 0.0),
                "timestamp": datetime.now().isoformat()
            }

            json_str = json.dumps(heartbeat_data, default=self._json_serializer)
            return json_str.encode('utf-8')

        except Exception as e:
            self.logger.error(f"Failed to serialize heartbeat: {e}")
            return b'{"type": "error", "message": "Heartbeat serialization failed"}'

    def deserialize_heartbeat(self, data: bytes) -> Dict[str, Any]:
        """Deserialize heartbeat from MT4"""
        try:
            json_str = data.decode('utf-8')
            heartbeat_data = json.loads(json_str)

            # Validate required fields
            if heartbeat_data.get("type") != "heartbeat":
                raise ValueError("Invalid heartbeat type")

            return heartbeat_data

        except Exception as e:
            self.logger.error(f"Failed to deserialize heartbeat: {e}")
            return {"type": "error", "message": "Heartbeat deserialization failed"}

    def serialize_response(self, response: Dict[str, Any]) -> bytes:
        """Serialize general response for ZMQ"""
        try:
            response_data = {
                "type": "response",
                "status": response.get("status", "unknown"),
                "message": response.get("message", ""),
                "data": response.get("data", {}),
                "timestamp": datetime.now().isoformat()
            }

            json_str = json.dumps(response_data, default=self._json_serializer)
            return json_str.encode('utf-8')

        except Exception as e:
            self.logger.error(f"Failed to serialize response: {e}")
            return b'{"type": "error", "message": "Response serialization failed"}'

    def serialize_signal_ws(self, signal: Dict[str, Any]) -> str:
        """Serialize signal for WebSocket transmission (JSON string)"""
        try:
            signal_data = {
                "type": "signal",
                "symbol": signal.get("symbol", ""),
                "action": signal.get("action", "HOLD"),
                "confidence": float(signal.get("confidence", 0.0)),
                "reason": signal.get("reason", ""),
                "server_timestamp": signal.get("server_timestamp", 0),
                "votes": signal.get("votes", {}),
                "metadata": signal.get("metadata", {})
            }

            return json.dumps(signal_data, default=self._json_serializer)

        except Exception as e:
            self.logger.error(f"Failed to serialize WebSocket signal: {e}")
            return '{"type": "error", "message": "WebSocket serialization failed"}'

    def deserialize_signal_ws(self, message: str) -> Dict[str, Any]:
        """Deserialize signal from WebSocket"""
        try:
            signal_data = json.loads(message)

            # Validate required fields
            if signal_data.get("type") != "signal":
                raise ValueError("Invalid WebSocket signal type")

            return signal_data

        except Exception as e:
            self.logger.error(f"Failed to deserialize WebSocket signal: {e}")
            return {"type": "error", "message": "WebSocket deserialization failed"}

    def _json_serializer(self, obj: Any) -> Union[str, float]:
        """Custom JSON serializer for datetime and other objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (int, float)):
            return obj
        else:
            return str(obj)


class ProtobufSerializer:
    """Protobuf-based serializer for high-performance scenarios"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def serialize_signal(self, signal: Dict[str, Any]) -> bytes:
        """Serialize signal using Protobuf"""
        try:
            # This would use actual protobuf definitions
            # For now, fall back to JSON
            json_str = json.dumps(signal, default=str)
            return json_str.encode('utf-8')
        except Exception as e:
            self.logger.error(f"Protobuf serialization failed: {e}")
            return b'{"type": "error", "message": "Protobuf serialization failed"}'

    def deserialize_signal(self, data: bytes) -> Dict[str, Any]:
        """Deserialize signal from Protobuf"""
        try:
            # This would use actual protobuf definitions
            # For now, fall back to JSON
            json_str = data.decode('utf-8')
            return json.loads(json_str)
        except Exception as e:
            self.logger.error(f"Protobuf deserialization failed: {e}")
            return {"type": "error", "message": "Protobuf deserialization failed"}


class CompressedSerializer:
    """Serializer with compression for bandwidth optimization"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_serializer = MessageSerializer()

    def serialize_signal(self, signal: Dict[str, Any]) -> bytes:
        """Serialize and compress signal"""
        try:
            import gzip

            # First serialize to JSON
            json_data = self.base_serializer.serialize_signal(signal)

            # Compress
            compressed = gzip.compress(json_data)

            return compressed

        except Exception as e:
            self.logger.error(f"Compressed serialization failed: {e}")
            return self.base_serializer.serialize_signal(signal)

    def deserialize_signal(self, data: bytes) -> Dict[str, Any]:
        """Decompress and deserialize signal"""
        try:
            import gzip

            # Try to decompress
            try:
                decompressed = gzip.decompress(data)
                return self.base_serializer.deserialize_signal(decompressed)
            except gzip.BadGzipFile:
                # Not compressed, try direct deserialization
                return self.base_serializer.deserialize_signal(data)

        except Exception as e:
            self.logger.error(f"Compressed deserialization failed: {e}")
            return {"type": "error", "message": "Compressed deserialization failed"}