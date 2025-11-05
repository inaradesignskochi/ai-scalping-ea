"""
Communication Layer - ZeroMQ primary with WebSocket fallback
Handles ultra-low latency communication between AI backend and MT4
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
import zmq
import zmq.asyncio
import websockets
from websockets.exceptions import ConnectionClosedError

from .config import settings
from .utils.message_serializer import MessageSerializer


class ZMQBridge:
    """ZeroMQ-based communication bridge for ultra-low latency"""

    def __init__(self):
        self.context = zmq.asyncio.Context()
        self.publisher = None
        self.responder = None
        self.running = False
        self.latency_samples = []
        self.message_serializer = MessageSerializer()
        self.logger = logging.getLogger(__name__)

        # Callbacks
        self.on_signal_request: Optional[Callable] = None
        self.on_heartbeat: Optional[Callable] = None

    async def start(self):
        """Start ZMQ bridge"""
        self.running = True
        self.logger.info("Starting ZeroMQ bridge...")

        try:
            # Publisher socket for sending signals to MT4
            self.publisher = self.context.socket(zmq.PUB)
            self.publisher.bind(settings.zmq_signal_address)
            self.logger.info(f"Publisher bound to {settings.zmq_signal_address}")

            # Responder socket for MT4 heartbeat/status
            self.responder = self.context.socket(zmq.REP)
            self.responder.bind(settings.zmq_heartbeat_address)
            self.logger.info(f"Responder bound to {settings.zmq_heartbeat_address}")

            # Start heartbeat handler
            asyncio.create_task(self._heartbeat_handler())

        except Exception as e:
            self.logger.error(f"Failed to start ZMQ bridge: {e}")
            raise

    async def stop(self):
        """Stop ZMQ bridge"""
        self.running = False

        if self.publisher:
            self.publisher.close()
        if self.responder:
            self.responder.close()

        self.context.term()
        self.logger.info("ZMQ bridge stopped")

    async def send_signal(self, signal: Dict[str, Any]) -> bool:
        """Send trading signal to MT4"""
        if not self.publisher or not self.running:
            return False

        try:
            # Add timestamp for latency tracking
            signal['server_timestamp'] = time.time_ns()

            # Serialize message
            message = self.message_serializer.serialize_signal(signal)

            # Send via PUB socket
            await self.publisher.send(message)

            # Log for monitoring
            self.logger.info(f"Signal sent: {signal['action']} {signal.get('symbol', 'N/A')} "
                           f"(confidence: {signal.get('confidence', 0):.2%})")

            return True

        except Exception as e:
            self.logger.error(f"Failed to send signal: {e}")
            return False

    async def _heartbeat_handler(self):
        """Handle heartbeat messages from MT4"""
        while self.running:
            try:
                # Wait for heartbeat message
                message = await self.responder.recv()

                # Deserialize
                heartbeat_data = self.message_serializer.deserialize_heartbeat(message)

                # Calculate latency
                if 'client_timestamp' in heartbeat_data:
                    latency_ns = time.time_ns() - heartbeat_data['client_timestamp']
                    latency_ms = latency_ns / 1_000_000
                    self.latency_samples.append(latency_ms)

                    # Keep only last 100 samples
                    if len(self.latency_samples) > 100:
                        self.latency_samples.pop(0)

                # Prepare response
                response = {
                    'status': 'OK',
                    'server_time': time.time_ns(),
                    'avg_latency_ms': sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0,
                    'timestamp': datetime.now().isoformat()
                }

                # Send response
                response_message = self.message_serializer.serialize_response(response)
                await self.responder.send(response_message)

                # Callback if registered
                if self.on_heartbeat:
                    await self.on_heartbeat(heartbeat_data, response)

            except zmq.ZMQError as e:
                if self.running:  # Only log if not shutting down
                    self.logger.error(f"ZMQ heartbeat error: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Heartbeat handler error: {e}")
                await asyncio.sleep(1)

    def get_latency_stats(self) -> Dict[str, float]:
        """Get latency statistics"""
        if not self.latency_samples:
            return {'avg': 0.0, 'min': 0.0, 'max': 0.0, 'count': 0}

        return {
            'avg': sum(self.latency_samples) / len(self.latency_samples),
            'min': min(self.latency_samples),
            'max': max(self.latency_samples),
            'count': len(self.latency_samples)
        }

    def is_healthy(self) -> bool:
        """Health check"""
        return self.running and self.publisher is not None and self.responder is not None


class WebSocketBridge:
    """WebSocket fallback communication bridge"""

    def __init__(self):
        self.server = None
        self.clients = set()
        self.running = False
        self.message_serializer = MessageSerializer()
        self.logger = logging.getLogger(__name__)

        # Callbacks
        self.on_signal_request: Optional[Callable] = None
        self.on_client_connected: Optional[Callable] = None
        self.on_client_disconnected: Optional[Callable] = None

    async def start(self):
        """Start WebSocket server"""
        self.running = True
        self.logger.info(f"Starting WebSocket bridge on {settings.websocket_address}")

        try:
            self.server = await websockets.serve(
                self._handle_client,
                settings.websocket_host,
                settings.websocket_port
            )
            self.logger.info("WebSocket server started")

        except Exception as e:
            self.logger.error(f"Failed to start WebSocket server: {e}")
            raise

    async def stop(self):
        """Stop WebSocket server"""
        self.running = False

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Disconnect all clients
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )
            self.clients.clear()

        self.logger.info("WebSocket bridge stopped")

    async def broadcast_signal(self, signal: Dict[str, Any]) -> int:
        """Broadcast signal to all connected clients"""
        if not self.running or not self.clients:
            return 0

        # Add timestamp
        signal['server_timestamp'] = time.time_ns()

        # Serialize message
        message = self.message_serializer.serialize_signal_ws(signal)

        # Send to all clients
        tasks = [self._send_to_client(client, message) for client in self.clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_sends = sum(1 for r in results if r is None)  # None means success

        self.logger.info(f"Signal broadcasted to {successful_sends}/{len(self.clients)} clients: "
                        f"{signal['action']} {signal.get('symbol', 'N/A')}")

        return successful_sends

    async def _send_to_client(self, client: websockets.WebSocketServerProtocol, message: str):
        """Send message to individual client"""
        try:
            await client.send(message)
        except Exception as e:
            # Remove disconnected client
            self.clients.discard(client)
            if self.on_client_disconnected:
                await self.on_client_disconnected(client)

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle individual client connection"""
        self.clients.add(websocket)

        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.logger.info(f"Client connected: {client_info}")

        if self.on_client_connected:
            await self.on_client_connected(websocket)

        try:
            async for message in websocket:
                try:
                    # Parse message
                    data = json.loads(message)

                    # Handle different message types
                    if data.get('type') == 'heartbeat':
                        await self._handle_heartbeat(websocket, data)
                    elif data.get('type') == 'status_request':
                        await self._handle_status_request(websocket, data)
                    elif data.get('type') == 'signal_ack':
                        await self._handle_signal_ack(websocket, data)
                    else:
                        self.logger.warning(f"Unknown message type: {data.get('type')}")

                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON from client {client_info}")
                except Exception as e:
                    self.logger.error(f"Error handling message from {client_info}: {e}")

        except ConnectionClosedError:
            self.logger.info(f"Client disconnected: {client_info}")
        except Exception as e:
            self.logger.error(f"Client handler error for {client_info}: {e}")
        finally:
            self.clients.discard(websocket)
            if self.on_client_disconnected:
                await self.on_client_disconnected(websocket)

    async def _handle_heartbeat(self, websocket: websockets.WebSocketServerProtocol, data: Dict[str, Any]):
        """Handle heartbeat from client"""
        response = {
            'type': 'heartbeat_response',
            'server_time': time.time_ns(),
            'client_timestamp': data.get('client_timestamp'),
            'status': 'OK'
        }

        await websocket.send(json.dumps(response))

    async def _handle_status_request(self, websocket: websockets.WebSocketServerProtocol, data: Dict[str, Any]):
        """Handle status request from client"""
        response = {
            'type': 'status_response',
            'server_time': time.time_ns(),
            'connected_clients': len(self.clients),
            'status': 'healthy' if self.running else 'unhealthy'
        }

        await websocket.send(json.dumps(response))

    async def _handle_signal_ack(self, websocket: websockets.WebSocketServerProtocol, data: Dict[str, Any]):
        """Handle signal acknowledgment from client"""
        # Log acknowledgment for monitoring
        self.logger.debug(f"Signal ACK received: {data.get('signal_id')}")

        # Could implement acknowledgment tracking here
        pass

    def get_client_count(self) -> int:
        """Get number of connected clients"""
        return len(self.clients)

    def is_healthy(self) -> bool:
        """Health check"""
        return self.running and self.server is not None


class CommunicationManager:
    """Unified communication manager with automatic failover"""

    def __init__(self):
        self.zmq_bridge = ZMQBridge()
        self.websocket_bridge = WebSocketBridge()
        self.active_bridge = 'zmq'  # 'zmq' or 'websocket'
        self.failover_enabled = True
        self.health_check_interval = 30  # seconds
        self.logger = logging.getLogger(__name__)
        self.running = False

    async def start(self):
        """Start communication manager"""
        self.running = True
        self.logger.info("Starting Communication Manager...")

        # Start both bridges
        await self.zmq_bridge.start()
        await self.websocket_bridge.start()

        # Start health monitoring
        asyncio.create_task(self._health_monitor())

        # Set up callbacks
        self._setup_callbacks()

    async def stop(self):
        """Stop communication manager"""
        self.running = False

        await self.zmq_bridge.stop()
        await self.websocket_bridge.stop()

        self.logger.info("Communication Manager stopped")

    async def send_signal(self, signal: Dict[str, Any]) -> bool:
        """Send signal using active bridge"""
        if self.active_bridge == 'zmq':
            success = await self.zmq_bridge.send_signal(signal)
            if not success and self.failover_enabled:
                self.logger.warning("ZMQ send failed, switching to WebSocket")
                self.active_bridge = 'websocket'
                return await self.websocket_bridge.broadcast_signal(signal) > 0
            return success

        elif self.active_bridge == 'websocket':
            success = await self.websocket_bridge.broadcast_signal(signal) > 0
            if not success and self.failover_enabled:
                self.logger.warning("WebSocket send failed, switching to ZMQ")
                self.active_bridge = 'zmq'
                return await self.zmq_bridge.send_signal(signal)
            return success

        return False

    async def _health_monitor(self):
        """Monitor bridge health and handle failover"""
        while self.running:
            try:
                zmq_healthy = self.zmq_bridge.is_healthy()
                ws_healthy = self.websocket_bridge.is_healthy()

                # Automatic failover logic
                if self.active_bridge == 'zmq' and not zmq_healthy and ws_healthy:
                    self.logger.warning("ZMQ bridge unhealthy, failing over to WebSocket")
                    self.active_bridge = 'websocket'

                elif self.active_bridge == 'websocket' and not ws_healthy and zmq_healthy:
                    self.logger.warning("WebSocket bridge unhealthy, failing over to ZMQ")
                    self.active_bridge = 'zmq'

                # Log health status
                self.logger.debug(f"Bridge health - ZMQ: {zmq_healthy}, WebSocket: {ws_healthy}, Active: {self.active_bridge}")

                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.health_check_interval)

    def _setup_callbacks(self):
        """Set up bridge callbacks"""

        # ZMQ heartbeat callback
        async def zmq_heartbeat_handler(heartbeat_data, response):
            latency_stats = self.zmq_bridge.get_latency_stats()
            self.logger.debug(f"ZMQ latency - Avg: {latency_stats['avg']:.2f}ms, "
                            f"Min: {latency_stats['min']:.2f}ms, Max: {latency_stats['max']:.2f}ms")

        self.zmq_bridge.on_heartbeat = zmq_heartbeat_handler

        # WebSocket connection callbacks
        async def ws_client_connected(client):
            self.logger.info(f"WebSocket client connected. Total clients: {self.websocket_bridge.get_client_count()}")

        async def ws_client_disconnected(client):
            self.logger.info(f"WebSocket client disconnected. Total clients: {self.websocket_bridge.get_client_count()}")

        self.websocket_bridge.on_client_connected = ws_client_connected
        self.websocket_bridge.on_client_disconnected = ws_client_disconnected

    def get_status(self) -> Dict[str, Any]:
        """Get communication status"""
        return {
            'active_bridge': self.active_bridge,
            'zmq_healthy': self.zmq_bridge.is_healthy(),
            'websocket_healthy': self.websocket_bridge.is_healthy(),
            'websocket_clients': self.websocket_bridge.get_client_count(),
            'zmq_latency_stats': self.zmq_bridge.get_latency_stats(),
            'failover_enabled': self.failover_enabled
        }

    def is_healthy(self) -> bool:
        """Overall health check"""
        return self.running and (
            self.zmq_bridge.is_healthy() or self.websocket_bridge.is_healthy()
        )