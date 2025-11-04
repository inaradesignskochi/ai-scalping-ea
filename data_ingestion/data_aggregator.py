import asyncio
import aiohttp
from redis import Redis
import websockets
from .sources import MT4TickStream, CryptoWebSocket, NewsAggregator, SocialScraper

class DataAggregator:
    def __init__(self):
        self.redis_client = Redis(host='localhost', port=6379, decode_responses=True)
        self.sources = {
            'mt4_ticks': MT4TickStream(),
            'crypto_ws': CryptoWebSocket(['binance', 'coinbase']),
            'news_apis': NewsAggregator([
                'marketaux', 'eodhd', 'fmp', 
                'newsapi', 'gdelt', 'alpaca'
            ]),
            'social_sentiment': SocialScraper(['reddit', 'twitter'])
        }
    
    async def start(self):
        tasks = [
            self.sources['mt4_ticks'].stream(),
            self.sources['crypto_ws'].stream(),
            self.sources['news_apis'].poll(),
            self.sources['social_sentiment'].poll()
        ]
        await asyncio.gather(*tasks)
    
    def publish_to_pipeline(self, data_type, data):
        """Push to Redis pub/sub for AI pipeline"""
        self.redis_client.publish(f'market_data:{data_type}', data)
        # Store in time-series for historical analysis
        self.redis_client.ts().add(f'ts:{data_type}', '*', data['value'])