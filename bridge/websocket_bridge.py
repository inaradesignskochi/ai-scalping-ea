import asyncio
import websockets

class WebSocketBridge:
    def __init__(self):
        pass

    async def start(self):
        async with websockets.serve(self.handler, "localhost", 8765):
            await asyncio.Future()  # run forever

    async def handler(self, websocket, path):
        async for message in websocket:
            print(f"Received message: {message}")