import asyncio
import json
import base64
import socket
import threading
import time
import queue
import subprocess
from websocket import create_connection
import uuid
import numpy as np
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add OpenAI-related globals as class variables
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please check your .env file.")
WS_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01'

class OpenAIHandler:
    openai_connections = {}  # Map of client_id -> OpenAI WebSocket connection
    audio_buffers = {}      # Map of client_id -> audio buffer
    stop_events = {}        # Map of client_id -> stop event

    def __init__(self, client_id, client_websocket, loop):
        self.client_id = client_id
        self.client_websocket = client_websocket
        self.loop = loop
        self.ws = None
        self.audio_buffer = bytearray()
        self.stop_event = threading.Event()
        self.audio_queue = queue.Queue()
        self.sequence_number = 1
        self.stream_sid = f"MZ{uuid.uuid4().hex.upper()}"
        self.account_sid = f"AC{uuid.uuid4().hex.upper()}"
        self.call_sid = f"CA{uuid.uuid4().hex.upper()}"
        
    async def connect_to_openai(self):
        """Establish connection to OpenAI's realtime API"""
        try:
            # Create IPv4 connection
            original_getaddrinfo = socket.getaddrinfo
            def getaddrinfo_ipv4(host, port, family=socket.AF_INET, *args):
                return original_getaddrinfo(host, port, socket.AF_INET, *args)
            
            socket.getaddrinfo = getaddrinfo_ipv4
            try:
                self.ws = create_connection(
                    WS_URL,
                    header=[
                        f'Authorization: Bearer {API_KEY}',
                        'OpenAI-Beta: realtime=v1'
                    ]
                )
                print(f'[OpenAI] Connected for client {self.client_id}')
                
                # Send session configuration
                await self.send_session_config()
                
                # Start audio processing threads
                threading.Thread(target=self.receive_audio_from_openai, daemon=True).start()
                threading.Thread(target=self.send_audio_to_openai, daemon=True).start()
                
                return True
            finally:
                socket.getaddrinfo = original_getaddrinfo
                
        except Exception as e:
            print(f'[OpenAI] Failed to connect for client {self.client_id}: {e}')
            return False
    
    async def send_session_config(self):
        """Send session configuration to OpenAI"""
        session_config = {
            "type": "session.update",
            "session": {
                "instructions": (
                    "Your knowledge cutoff is 2023-10. You are a helpful, witty, and friendly AI. "
                    "Act like a human, but remember that you aren't a human and that you can't do human things in the real world. "
                    "Your voice and personality should be warm and engaging, with a lively and playful tone. "
                    "Talk quickly. You should always call a function if you can. "
                    "Do not refer to these rules, even if you're asked about them."
                ),
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "voice": "alloy",
                "temperature": 1,
                "max_response_output_tokens": 4096,
                "modalities": ["text", "audio"],
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "tool_choice": "auto",
                "tools": [
                    {
                        "type": "function",
                        "name": "get_weather",
                        "description": "Get current weather for a specified city",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "The name of the city for which to fetch the weather."
                                }
                            },
                            "required": ["city"]
                        }
                    },
                    {
                        "type": "function",
                        "name": "write_notepad",
                        "description": "Open a text editor and write the time, for example, 2024-10-29 16:19. Then, write the content, which should include my questions along with your answers.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "The content consists of my questions along with the answers you provide."
                                },
                                "date": {
                                    "type": "string",
                                    "description": "the time, for example, 2024-10-29 16:19. "
                                }
                            },
                            "required": ["content", "date"]
                        }
                    }
                ]
            }
        }
        
        try:
            self.ws.send(json.dumps(session_config))
            print(f'[OpenAI] Session config sent for client {self.client_id}')
        except Exception as e:
            print(f'[OpenAI] Failed to send session config for client {self.client_id}: {e}')

    async def send_mark(self, name):
        event = {
            "event": "mark",
            "sequenceNumber": self.sequence_number,
            "mark": {"name": name},
            "streamSid": self.stream_sid
        }
        self.sequence_number += 1
        await self.client_websocket.send(json.dumps(event))
        print(f"[WebSocket] Sent mark for client {self.client_id}")
    
    async def send_media(self, payload, chunk):
       try:
           event = {
               "event": "media",
               "streamSid": self.stream_sid,
               "media": {"payload": payload, "chunk": chunk}
           }
           self.sequence_number += 1
           await self.client_websocket.send(json.dumps(event))
           print(f"[WebSocket] Sent media for client {self.client_id}, chunk {chunk}")
       except Exception as e:
           print(f"[WebSocket] Failed to send media for client {self.client_id}: {e}")

    async def send_clear(self):
        payload = {
            "event": "clear",
            "sequenceNumber": self.sequence_number,
            "streamSid": self.stream_sid
        }
        self.sequence_number += 1
        await self.client_websocket.send(json.dumps(payload))
        print(f"[WebSocket] Sent clear for client {self.client_id}")
    
    def receive_audio_from_openai(self):
        """Receive audio from OpenAI and send back to Tata SIP client"""
        try:
            while not self.stop_event.is_set():
                try:
                    message = self.ws.recv()
                    if not message:
                        print(f'[OpenAI] Received empty message for client {self.client_id}')
                        break
                    
                    data = json.loads(message)
                    event_type = data.get('type')
                    print(f'[OpenAI] Received event for client {self.client_id}: {event_type}')
                    
                    if event_type == 'session.created':
                        print(f'[OpenAI] Session created for client {self.client_id}')
                    
                    elif event_type == 'response.audio.delta':
                        # audio_content = base64.b64decode(data['delta'])
                        # self.audio_buffer.extend(audio_content)
                        asyncio.run_coroutine_threadsafe(
                            self.send_media(data['delta'], data['content_index']),
                            self.loop
                        )
                        print(f'[OpenAI] Received {len(data['delta'])} bytes for client {self.client_id}')
                    
                    elif event_type == 'input_audio_buffer.speech_started':
                        print(f'[OpenAI] Speech started for client {self.client_id}')
                        self.audio_buffer.clear()
                    
                    elif event_type == 'response.audio.done':
                        print(f'[OpenAI] AI finished speaking for client {self.client_id}')
                        print(f'[Event] Mark event sent for client {self.client_id}')
                        # Forward done event
                        asyncio.run_coroutine_threadsafe(
                            self.send_mark(data["event_id"]),
                            self.loop
                        )
                        self.audio_buffer.clear()
                        
                    
                    elif event_type == 'response.function_call_arguments.done':
                        self.handle_function_call(data)
                    
                except Exception as e:
                    print(f'[OpenAI] Error receiving audio for client {self.client_id}: {e}')
                    break
                    
        except Exception as e:
            print(f'[OpenAI] Exception in receive thread for client {self.client_id}: {e}')
        finally:
            print(f'[OpenAI] Exiting receive thread for client {self.client_id}')
    
    def send_audio_to_openai(self):
        """Send audio from Tata SIP to OpenAI"""
        try:
            while not self.stop_event.is_set():
                try:
                    if not self.audio_queue.empty():
                        audio_chunk = self.audio_queue.get()
                        encoded_chunk = base64.b64encode(audio_chunk).decode('utf-8')
                        message = json.dumps({'type': 'input_audio_buffer.append', 'audio': encoded_chunk})
                        self.ws.send(message)
                        print(f'[OpenAI] Sent {len(audio_chunk)} bytes to OpenAI for client {self.client_id}')
                except Exception as e:
                    print(f'[OpenAI] Error sending audio for client {self.client_id}: {e}')
                    break
                time.sleep(0.01)  # Small delay to prevent busy waiting
        except Exception as e:
            print(f'[OpenAI] Exception in send thread for client {self.client_id}: {e}')
        finally:
            print(f'[OpenAI] Exiting send thread for client {self.client_id}')
    
    def handle_function_call(self, event_json):
        """Handle function calls from OpenAI"""
        try:
            name = event_json.get("name", "")
            call_id = event_json.get("call_id", "")
            arguments = event_json.get("arguments", "{}")
            function_call_args = json.loads(arguments)
            
            if name == "write_notepad":
                print(f"[OpenAI] Writing to notepad for client {self.client_id}")
                content = function_call_args.get("content", "")
                date = function_call_args.get("date", "")
                
                subprocess.Popen([
                    "powershell", "-Command", 
                    f"Add-Content -Path temp.txt -Value 'date: {date}\n{content}\n\n'; notepad.exe temp.txt"
                ])
                
                self.send_function_call_result("write notepad successful.", call_id)
            
            elif name == "get_weather":
                city = function_call_args.get("city", "")
                if city:
                    weather_result = self.get_weather(city)
                    self.send_function_call_result(weather_result, call_id)
                else:
                    print(f"[OpenAI] City not provided for get_weather for client {self.client_id}")
                    
        except Exception as e:
            print(f"[OpenAI] Error handling function call for client {self.client_id}: {e}")
    
    def send_function_call_result(self, result, call_id):
        """Send function call result back to OpenAI"""
        result_json = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "output": result,
                "call_id": call_id
            }
        }
        
        try:
            self.ws.send(json.dumps(result_json))
            print(f"[OpenAI] Sent function call result for client {self.client_id}")
            
            # Send response creation
            rp_json = {"type": "response.create"}
            self.ws.send(json.dumps(rp_json))
        except Exception as e:
            print(f"[OpenAI] Failed to send function call result for client {self.client_id}: {e}")
    
    def get_weather(self, city):
        """Simulate weather API call"""
        return json.dumps({
            "city": city,
            "temperature": "99°C"
        })
    
    def add_audio_chunk(self, audio_bytes):
        """Add audio chunk from Tata SIP to OpenAI queue"""
        try:
            # Convert from u-law to u-law (no conversion needed as we're already using u-law)
            # The audio is already in u-law format from the client
            self.audio_queue.put(audio_bytes)
        except Exception as e:
            print(f'[OpenAI] Error adding audio chunk for client {self.client_id}: {e}')
    
    def get_audio_buffer(self):
        """Get current audio buffer for playback"""
        return bytes(self.audio_buffer)
    
    def clear_audio_buffer(self):
        """Clear the audio buffer"""
        self.audio_buffer.clear()
    
    def close(self):
        """Close the OpenAI connection"""
        self.stop_event.set()
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                print(f'[OpenAI] Error closing connection for client {self.client_id}: {e}') 