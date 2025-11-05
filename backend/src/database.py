"""
Database connection and management utilities
Handles PostgreSQL/TimescaleDB connections and operations
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict, List
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, execute_values

from .config import settings


class DatabaseManager:
    """Database connection manager with connection pooling"""

    def __init__(self):
        self.connection_pool: Optional[pool.SimpleConnectionPool] = None
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.connection_pool = pool.SimpleConnectionPool(
                minconn=5,
                maxconn=20,
                host="postgres",
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.db_password
            )

            # Test connection
            conn = self.get_connection()
            if conn:
                conn.close()
                self.logger.info("Database connection pool initialized")
            else:
                raise Exception("Failed to establish database connection")

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            self.logger.info("Database connection pool closed")

    def get_connection(self):
        """Get a database connection from the pool"""
        if not self.connection_pool:
            raise Exception("Database not initialized")

        try:
            return self.connection_pool.getconn()
        except Exception as e:
            self.logger.error(f"Failed to get database connection: {e}")
            raise

    def return_connection(self, conn):
        """Return connection to the pool"""
        if self.connection_pool and conn:
            self.connection_pool.putconn(conn)

    @asynccontextmanager
    async def get_cursor(self, cursor_factory=None):
        """Context manager for database cursors"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=cursor_factory)
            yield cursor
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)


# Global database manager instance
db_manager = DatabaseManager()


async def init_db():
    """Initialize database connections"""
    await db_manager.initialize()


async def close_db():
    """Close database connections"""
    await db_manager.close()


class TradeRepository:
    """Repository for trade-related database operations"""

    @staticmethod
    async def save_trade_history(trade_data: Dict[str, Any]) -> bool:
        """Save trade to history table"""
        try:
            async with db_manager.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO trade_history (
                        trade_id, symbol, action, entry_price, exit_price,
                        lot_size, pnl, commission, swap, entry_time, exit_time,
                        duration_minutes, confidence, reason, agent_signals,
                        ticket_number, magic_number, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    trade_data['trade_id'],
                    trade_data['symbol'],
                    trade_data['action'],
                    trade_data['entry_price'],
                    trade_data.get('exit_price'),
                    trade_data['lot_size'],
                    trade_data.get('pnl'),
                    trade_data.get('commission', 0),
                    trade_data.get('swap', 0),
                    trade_data['entry_time'],
                    trade_data.get('exit_time'),
                    trade_data.get('duration_minutes'),
                    trade_data.get('confidence'),
                    trade_data.get('reason'),
                    psycopg2.extras.Json(trade_data.get('agent_signals', {})),
                    trade_data.get('ticket_number'),
                    trade_data.get('magic_number', settings.magic_number),
                    trade_data.get('status', 'open')
                ))
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save trade: {e}")
            return False

    @staticmethod
    async def update_trade_status(trade_id: str, status: str, exit_price: float = None,
                                pnl: float = None) -> bool:
        """Update trade status"""
        try:
            async with db_manager.get_cursor() as cursor:
                if status == 'closed':
                    cursor.execute("""
                        UPDATE trade_history
                        SET status = %s, exit_price = %s, pnl = %s, exit_time = NOW(),
                            duration_minutes = EXTRACT(EPOCH FROM (NOW() - entry_time))/60
                        WHERE trade_id = %s
                    """, (status, exit_price, pnl, trade_id))
                else:
                    cursor.execute("""
                        UPDATE trade_history
                        SET status = %s
                        WHERE trade_id = %s
                    """, (status, trade_id))
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to update trade status: {e}")
            return False

    @staticmethod
    async def get_recent_trades(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trades"""
        try:
            async with db_manager.get_cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM trade_history
                    ORDER BY entry_time DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get recent trades: {e}")
            return []


class MarketDataRepository:
    """Repository for market data operations"""

    @staticmethod
    async def save_market_data(data_points: List[Dict[str, Any]]) -> bool:
        """Save market data points"""
        if not data_points:
            return True

        try:
            async with db_manager.get_cursor() as cursor:
                # Prepare data for bulk insert
                values = []
                for point in data_points:
                    values.append((
                        point['time'],
                        point['symbol'],
                        point.get('price'),
                        point.get('volume'),
                        point.get('bid'),
                        point.get('ask'),
                        point.get('spread'),
                        point['data_type']
                    ))

                execute_values(cursor,
                    "INSERT INTO market_data (time, symbol, price, volume, bid, ask, spread, data_type) VALUES %s",
                    values)

            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save market data: {e}")
            return False

    @staticmethod
    async def get_price_history(symbol: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get price history for symbol"""
        try:
            async with db_manager.get_cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM market_data
                    WHERE symbol = %s AND data_type = 'tick'
                    ORDER BY time DESC
                    LIMIT %s
                """, (symbol, limit))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get price history: {e}")
            return []


class ModelRepository:
    """Repository for AI model management"""

    @staticmethod
    async def get_active_models() -> List[Dict[str, Any]]:
        """Get all active models"""
        try:
            async with db_manager.get_cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM model_registry
                    WHERE status = 'active'
                    ORDER BY performance_score DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get active models: {e}")
            return []

    @staticmethod
    async def update_model_performance(agent_name: str, performance_score: float) -> bool:
        """Update model performance score"""
        try:
            async with db_manager.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE model_registry
                    SET performance_score = %s, updated_at = NOW()
                    WHERE agent_name = %s
                """, (performance_score, agent_name))
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to update model performance: {e}")
            return False

    @staticmethod
    async def switch_model(agent_name: str, new_model_path: str, version: str) -> bool:
        """Switch active model for agent"""
        try:
            async with db_manager.get_cursor() as cursor:
                # Deactivate current model
                cursor.execute("""
                    UPDATE model_registry
                    SET status = 'inactive'
                    WHERE agent_name = %s AND status = 'active'
                """, (agent_name,))

                # Activate new model
                cursor.execute("""
                    UPDATE model_registry
                    SET status = 'active', model_path = %s, version = %s, updated_at = NOW()
                    WHERE agent_name = %s
                """, (new_model_path, version, agent_name))

            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to switch model: {e}")
            return False


class PerformanceRepository:
    """Repository for performance metrics"""

    @staticmethod
    async def save_ai_performance(agent_name: str, metric_name: str, value: float,
                                metadata: Dict[str, Any] = None) -> bool:
        """Save AI performance metric"""
        try:
            async with db_manager.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ai_performance (timestamp, agent_name, metric_name, metric_value, metadata)
                    VALUES (NOW(), %s, %s, %s, %s)
                """, (agent_name, metric_name, value, psycopg2.extras.Json(metadata or {})))
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save AI performance: {e}")
            return False

    @staticmethod
    async def save_system_health(component: str, metric_name: str, value: float,
                               status: str = 'healthy', message: str = '') -> bool:
        """Save system health metric"""
        try:
            async with db_manager.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO system_health (timestamp, component, metric_name, metric_value, status, message)
                    VALUES (NOW(), %s, %s, %s, %s, %s)
                """, (component, metric_name, value, status, message))
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to save system health: {e}")
            return False