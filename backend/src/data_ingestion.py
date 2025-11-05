"""
Data Ingestion Layer - Multi-source data aggregator
Collects and processes data from various sources for AI analysis
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import websockets
import redis
import psycopg2
from psycopg2.extras import execute_values

from .config import settings
from .utils.rate_limiter import RateLimiter


class DataSource(ABC):
    """Abstract base class for data sources"""

    def __init__(self, name: str, rate_limit: int = 60):
        self.name = name
        self.rate_limiter = RateLimiter(rate_limit)
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from the source"""
        pass

    @abstractmethod
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate data format"""
        pass


class MT4TickStream(DataSource):
    """MT4 native tick data stream"""

    def __init__(self):
        super().__init__("mt4_ticks", rate_limit=1000)  # High frequency
        self.websocket_url = f"ws://{settings.mt4_server_ip}:8080" if settings.mt4_server_ip else None

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Stream real-time tick data from MT4"""
        if not self.websocket_url:
            return []

        try:
            async with websockets.connect(self.websocket_url) as websocket:
                await websocket.send(json.dumps({"type": "subscribe", "symbol": "*"}))

                ticks = []
                for _ in range(100):  # Collect 100 ticks
                    if not await self.rate_limiter.acquire():
                        break

                    message = await websocket.recv()
                    data = json.loads(message)

                    if self.validate_data(data):
                        ticks.append({
                            "symbol": data["symbol"],
                            "price": data["price"],
                            "volume": data["volume"],
                            "timestamp": datetime.fromisoformat(data["timestamp"]),
                            "data_type": "tick"
                        })

                return ticks

        except Exception as e:
            self.logger.error(f"Error fetching MT4 ticks: {e}")
            return []

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate tick data"""
        required_fields = ["symbol", "price", "volume", "timestamp"]
        return all(field in data for field in required_fields)


class CryptoWebSocket(DataSource):
    """Cryptocurrency WebSocket feeds"""

    def __init__(self, exchanges: List[str] = None):
        super().__init__("crypto_ws", rate_limit=500)
        self.exchanges = exchanges or ["binance", "coinbase"]
        self.exchange_urls = {
            "binance": "wss://stream.binance.com:9443/ws/!ticker@arr",
            "coinbase": "wss://ws-feed.pro.coinbase.com"
        }

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch crypto price data"""
        all_data = []

        for exchange in self.exchanges:
            if exchange in self.exchange_urls:
                data = await self._fetch_exchange_data(exchange)
                all_data.extend(data)

        return all_data

    async def _fetch_exchange_data(self, exchange: str) -> List[Dict[str, Any]]:
        """Fetch data from specific exchange"""
        try:
            url = self.exchange_urls[exchange]
            async with websockets.connect(url) as websocket:
                if exchange == "binance":
                    await websocket.send(json.dumps({
                        "method": "SUBSCRIBE",
                        "params": ["!ticker@arr"],
                        "id": 1
                    }))

                data_points = []
                for _ in range(50):  # Collect 50 data points
                    if not await self.rate_limiter.acquire():
                        break

                    message = await websocket.recv()
                    data = json.loads(message)

                    if self.validate_data(data):
                        data_points.append({
                            "symbol": data.get("s", data.get("product_id", "")),
                            "price": float(data.get("c", data.get("price", 0))),
                            "volume": float(data.get("v", data.get("volume", 0))),
                            "timestamp": datetime.now(),
                            "data_type": "crypto_tick",
                            "exchange": exchange
                        })

                return data_points

        except Exception as e:
            self.logger.error(f"Error fetching {exchange} data: {e}")
            return []

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate crypto data"""
        return "price" in data or "c" in data


class NewsAggregator(DataSource):
    """Multi-source news and financial data aggregator"""

    def __init__(self, sources: List[str] = None):
        super().__init__("news_api", rate_limit=10)  # Respect API limits
        self.sources = sources or ["marketaux", "eodhd", "fmp", "newsapi", "gdelt"]
        self.api_keys = {
            "marketaux": settings.marketaux_api_key,
            "eodhd": settings.eodhd_api_key,
            "fmp": settings.fmp_api_key,
            "newsapi": settings.newsapi_api_key,
            "gdelt": settings.gdelt_api_key
        }

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch news from multiple sources"""
        all_news = []

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_source_news(session, source) for source in self.sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)

        return all_news

    async def _fetch_source_news(self, session: aiohttp.ClientSession, source: str) -> List[Dict[str, Any]]:
        """Fetch news from specific source"""
        if not self.api_keys.get(source):
            return []

        try:
            if not await self.rate_limiter.acquire():
                return []

            url, params = self._build_api_request(source)

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_news_response(source, data)
                else:
                    self.logger.warning(f"{source} API error: {response.status}")
                    return []

        except Exception as e:
            self.logger.error(f"Error fetching {source} news: {e}")
            return []

    def _build_api_request(self, source: str) -> tuple:
        """Build API request for specific source"""
        base_urls = {
            "marketaux": "https://api.marketaux.com/v1/news/all",
            "newsapi": "https://newsapi.org/v2/everything",
            "eodhd": "https://eodhd.com/api/news",
            "fmp": "https://financialmodelingprep.com/api/v3/stock_news",
            "gdelt": "https://api.gdeltproject.org/api/v2/doc/doc"
        }

        params = {
            "marketaux": {
                "api_token": self.api_keys["marketaux"],
                "symbols": "EURUSD,GBPUSD,BTCUSD,ETHUSD",
                "language": "en"
            },
            "newsapi": {
                "apiKey": self.api_keys["newsapi"],
                "q": "EURUSD OR GBPUSD OR BTCUSD OR ETHUSD",
                "language": "en",
                "sortBy": "publishedAt"
            },
            "eodhd": {
                "api_token": self.api_keys["eodhd"],
                "s": "EURUSD.FOREX,GBPUSD.FOREX,BTCUSD.CC,ETHUSD.CC"
            },
            "fmp": {
                "apikey": self.api_keys["fmp"]
            },
            "gdelt": {
                "query": "EURUSD OR GBPUSD OR BTCUSD OR ETHUSD",
                "mode": "artlist",
                "format": "json"
            }
        }

        return base_urls[source], params[source]

    def _parse_news_response(self, source: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse news response from specific source"""
        news_items = []

        try:
            articles = []
            if source == "marketaux":
                articles = data.get("data", [])
            elif source == "newsapi":
                articles = data.get("articles", [])
            elif source == "eodhd":
                articles = data.get("articles", [])
            elif source == "fmp":
                articles = data
            elif source == "gdelt":
                articles = data.get("articles", [])

            for article in articles[:10]:  # Limit to 10 articles per source
                news_item = {
                    "source": source,
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", article.get("published_at", datetime.now().isoformat())),
                    "sentiment": 0.0,  # Will be analyzed by AI
                    "relevance_score": 0.5,
                    "data_type": "news"
                }

                if self.validate_data(news_item):
                    news_items.append(news_item)

        except Exception as e:
            self.logger.error(f"Error parsing {source} response: {e}")

        return news_items

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate news data"""
        return bool(data.get("title") and data.get("url"))


class SocialScraper(DataSource):
    """Social media sentiment scraper"""

    def __init__(self, platforms: List[str] = None):
        super().__init__("social_sentiment", rate_limit=30)
        self.platforms = platforms or ["reddit", "twitter"]

    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch social media sentiment data"""
        all_sentiment = []

        for platform in self.platforms:
            if platform == "reddit":
                data = await self._fetch_reddit_data()
            elif platform == "twitter":
                data = await self._fetch_twitter_data()
            else:
                continue

            all_sentiment.extend(data)

        return all_sentiment

    async def _fetch_reddit_data(self) -> List[Dict[str, Any]]:
        """Fetch Reddit sentiment data"""
        # Simplified implementation - in production would use PRAW
        return []

    async def _fetch_twitter_data(self) -> List[Dict[str, Any]]:
        """Fetch Twitter sentiment data"""
        # Simplified implementation - in production would use Tweepy
        return []

    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate social data"""
        return bool(data.get("text") and data.get("platform"))


class DataAggregator:
    """Main data aggregation orchestrator"""

    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.redis_url)
        self.db_conn = None
        self.sources = {
            'mt4_ticks': MT4TickStream(),
            'crypto_ws': CryptoWebSocket(),
            'news_apis': NewsAggregator(),
            'social_sentiment': SocialScraper()
        }
        self.logger = logging.getLogger(__name__)
        self.running = False

    async def start(self):
        """Start data aggregation"""
        self.running = True
        self.logger.info("Starting data aggregation...")

        # Connect to database
        try:
            self.db_conn = psycopg2.connect(settings.db_connection_string)
            self.logger.info("Connected to database")
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            raise

        # Start aggregation loop
        asyncio.create_task(self._aggregation_loop())

    async def stop(self):
        """Stop data aggregation"""
        self.running = False
        if self.db_conn:
            self.db_conn.close()
        self.logger.info("Data aggregation stopped")

    async def _aggregation_loop(self):
        """Main aggregation loop"""
        while self.running:
            try:
                # Collect data from all sources
                tasks = [source.fetch_data() for source in self.sources.values()]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                all_data = []
                for result in results:
                    if isinstance(result, list):
                        all_data.extend(result)

                # Store data
                if all_data:
                    await self._store_data(all_data)
                    await self._publish_to_redis(all_data)

                # Wait before next cycle
                await asyncio.sleep(1)  # 1 second intervals

            except Exception as e:
                self.logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(5)  # Wait before retry

    async def _store_data(self, data: List[Dict[str, Any]]):
        """Store data in TimescaleDB"""
        if not self.db_conn:
            return

        try:
            # Prepare data for insertion
            market_data = []
            news_data = []

            for item in data:
                if item["data_type"] in ["tick", "crypto_tick"]:
                    market_data.append((
                        item["timestamp"],
                        item["symbol"],
                        item.get("price"),
                        item.get("volume"),
                        item.get("bid"),
                        item.get("ask"),
                        item.get("spread"),
                        item["data_type"]
                    ))
                elif item["data_type"] == "news":
                    news_data.append((
                        item["timestamp"],
                        item.get("symbol"),
                        item["title"],
                        item.get("description", ""),
                        item.get("content", ""),
                        item.get("sentiment", 0.0),
                        item.get("relevance_score", 0.5),
                        item["url"],
                        json.dumps(item.get("metadata", {}))
                    ))

            # Insert market data
            if market_data:
                with self.db_conn.cursor() as cursor:
                    execute_values(cursor,
                        "INSERT INTO market_data (time, symbol, price, volume, bid, ask, spread, data_type) VALUES %s",
                        market_data)

            # Insert news data
            if news_data:
                with self.db_conn.cursor() as cursor:
                    execute_values(cursor,
                        "INSERT INTO news_sentiment (timestamp, symbol, headline, content, sentiment, relevance_score, url, metadata) VALUES %s",
                        news_data)

            self.db_conn.commit()

        except Exception as e:
            self.logger.error(f"Error storing data: {e}")
            self.db_conn.rollback()

    async def _publish_to_redis(self, data: List[Dict[str, Any]]):
        """Publish data to Redis for AI pipeline"""
        try:
            for item in data:
                # Publish to appropriate channels
                channel = f"market_data:{item['data_type']}"
                self.redis_client.publish(channel, json.dumps(item))

                # Store in time-series
                if "price" in item:
                    self.redis_client.ts().add(
                        f"ts:{item['symbol']}:{item['data_type']}",
                        int(item['timestamp'].timestamp() * 1000),
                        item['price']
                    )

        except Exception as e:
            self.logger.error(f"Error publishing to Redis: {e}")

    def is_healthy(self) -> bool:
        """Health check"""
        return self.running and self.db_conn is not None