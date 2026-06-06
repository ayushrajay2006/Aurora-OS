import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect('ws://localhost:8765') as ws:
            prompts = [
                "can you open notepad",
                "search for files named stress",
                "what is 15 * 24?",
                "search the web for python documentation",
                "read the contents of D:\\Aurora\\main.py"
            ]
            for i, text in enumerate(prompts):
                print(f'Sending prompt {i+1}...')
                await ws.send(json.dumps({'event': 'user_command', 'payload': {'text': text}}))
                await asyncio.sleep(8)
            print('Sent all messages')
    except Exception as e:
        print(f"Failed: {e}")

asyncio.run(test())
