import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect('ws://localhost:8765') as ws:
            await ws.send(json.dumps({'event': 'user_command', 'payload': {'text': 'remember that my favorite color is blue'}}))
            print('Sent message')
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(test())
