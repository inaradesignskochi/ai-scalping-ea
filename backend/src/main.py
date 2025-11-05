#!/usr/bin/env python3
"""
AI Scalping EA Backend - Main Entry Point
Production-ready ultra-low latency trading system
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
import uvicorn

from .config import settings
from .database import init_db, close_db
from .data_ingestion import DataAggregator
from .ai_orchestrator import AIOrchestrator
from .communication import ZMQBridge, WebSocketBridge
from .monitoring import MonitoringService
from .utils.logger import setup_logging

# Global variables for graceful shutdown
data_aggregator: Optional[DataAggregator] = None
ai_orchestrator: Optional[AIOrchestrator] = None
zmq_bridge: Optional[ZMQBridge] = None
websocket_bridge: Optional[WebSocketBridge] = None
monitoring_service: Optional[MonitoringService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    global data_aggregator, ai_orchestrator, zmq_bridge, websocket_bridge, monitoring_service

    # Startup
    logger = logging.getLogger(__name__)
    logger.info("Starting AI Scalping EA Backend...")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Initialize components
        data_aggregator = DataAggregator()
        ai_orchestrator = AIOrchestrator()
        zmq_bridge = ZMQBridge()
        websocket_bridge = WebSocketBridge()
        monitoring_service = MonitoringService()

        # Start services
        await data_aggregator.start()
        await ai_orchestrator.start()
        await zmq_bridge.start()
        await websocket_bridge.start()
        await monitoring_service.start()

        logger.info("All services started successfully")

        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down AI Scalping EA Backend...")

        # Stop services gracefully
        tasks = []
        if monitoring_service:
            tasks.append(monitoring_service.stop())
        if websocket_bridge:
            tasks.append(websocket_bridge.stop())
        if zmq_bridge:
            tasks.append(zmq_bridge.stop())
        if ai_orchestrator:
            tasks.append(ai_orchestrator.stop())
        if data_aggregator:
            tasks.append(data_aggregator.stop())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Close database connections
        await close_db()

        logger.info("Shutdown complete")

def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="AI Scalping EA Backend",
        description="Ultra-low latency AI-powered trading system",
        version="1.0.0",
        lifespan=lifespan
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "1.0.0"}

    # System status endpoint
    @app.get("/status")
    async def system_status():
        return {
            "data_aggregator": data_aggregator.is_healthy() if data_aggregator else False,
            "ai_orchestrator": ai_orchestrator.is_healthy() if ai_orchestrator else False,
            "zmq_bridge": zmq_bridge.is_healthy() if zmq_bridge else False,
            "websocket_bridge": websocket_bridge.is_healthy() if websocket_bridge else False,
            "monitoring": monitoring_service.is_healthy() if monitoring_service else False
        }

    return app

def main():
    """Main entry point"""
    # Setup logging
    setup_logging()

    # Create application
    app = create_app()

    # Signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger = logging.getLogger(__name__)
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()