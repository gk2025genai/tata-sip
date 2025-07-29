import asyncio
import websockets
import json
import base64
import socket
import threading
import time
import queue
import subprocess
from websocket import create_connection
import socks
import uuid

# Set up SOCKS5 proxy (if needed)
# socket.socket = socks.socksocket

# Audio configuration
CHUNK_SIZE = 1024
RATE = 24000
FORMAT = 16  # pcm16

# Remove OpenAI-related globals from this file
# Remove openai_connections, audio_buffers, stop_events, API_KEY, WS_URL from this file
from openai_handler import OpenAIHandler

# WebSocket handler for Tata SIP
async def handler(websocket, path):
    client_id = id(websocket)
    print(f"[WebSocket] Connection established for client {client_id}")
    loop = asyncio.get_running_loop()
    openai_handler = OpenAIHandler(client_id, websocket, loop)
    OpenAIHandler.openai_connections[client_id] = openai_handler

    if not await openai_handler.connect_to_openai():
        print(f"[WebSocket] Failed to connect to OpenAI for client {client_id}")
        return
    
    try:
        async for message in websocket:
            data = json.loads(message)
            event_type = data.get("event")
            print(f"[WebSocket] Event for client {client_id}: {event_type}")

            if event_type == "media":
                media = data.get("media", {})
                audio_payload = media.get("payload", "")
                chunk = media.get("chunk", 1)
                timestamp = media.get("timestamp", 0)
                print(f"[Event] Received Audio from {client_id}")
                if audio_payload:
                    audio_bytes = base64.b64decode(audio_payload)
                    openai_handler.add_audio_chunk(audio_bytes)
                    print(f"[Event] Sent {len(audio_bytes)} bytes to OpenAI for client {client_id}")
            # elif event_type == "dtmf":
            #     digit = data.get("dtmf", {}).get("digit")
            #     print(f"[Event] DTMF received for client {client_id}: {digit}")
            #     await openai_handler.send_dtmf(digit)
            elif event_type == "stop":
                reason = data.get("stop", {}).get("reason")
                print(f"[Event] Call ended for client {client_id}: {reason}")
                await openai_handler.send_stop(reason)
            elif event_type == "mark":
                label = data.get("mark", {}).get("name")
                print(f"[Event] Received mark for client {client_id}: {label}")
                await openai_handler.send_mark(label)
            elif event_type == "clear":
                print(f"[Event] Clear audio buffer request received for client {client_id}")
                openai_handler.clear_audio_buffer()
                await openai_handler.send_clear()
            # ... handle other events as needed ...
            else:
                print(f"[Warning] Unknown event type for client {client_id}: {event_type}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"[WebSocket] Connection closed for client {client_id}: {e}")
    finally:
        # Clean up OpenAI connection
        if client_id in OpenAIHandler.openai_connections:
            OpenAIHandler.openai_connections[client_id].close()
            del OpenAIHandler.openai_connections[client_id]
        print(f"[WebSocket] Cleaned up client {client_id}")

# Start WebSocket server
async def main():
    port = 8766
    print(f"Starting Tata SIP + OpenAI WebSocket server on port {port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main()) 