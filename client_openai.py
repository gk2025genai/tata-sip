import asyncio
import websockets
import json
import base64
import sounddevice as sd
import numpy as np
import sys

SAMPLE_RATE = 24000  # Match server config
CHANNELS = 1
DTYPE = 'int16'
CHUNK_DURATION = 2  # seconds to record per push-to-talk
received_chunks = []
async def record_audio(duration=CHUNK_DURATION):
    print(f"[Client] Recording for {duration} seconds...")
    audio = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()
    return audio.flatten()

def encode_audio(audio_np):
    return base64.b64encode(audio_np.tobytes()).decode('utf-8')

def decode_audio(b64_audio):
    audio_bytes = base64.b64decode(b64_audio)
    return np.frombuffer(audio_bytes, dtype=DTYPE)
    return audio_bytes

def play_audio(audio_np):
    print(f"[Client] Playing response audio...")
    sd.play(audio_np, samplerate=SAMPLE_RATE)
    sd.wait()

async def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = sys.argv[2] if len(sys.argv) > 2 else "8766"
    uri = f"ws://{host}:{port}"
    print(f"[Client] Connecting to {uri}")
    async with websockets.connect(uri) as websocket:
        # Send connected event
        await websocket.send(json.dumps({"event": "connected"}))
        await asyncio.sleep(0.2)
        # Send start event (minimal)
        await websocket.send(json.dumps({"event": "start", "start": {"from": "mic", "to": "server"}}))
        await asyncio.sleep(0.2)
        # Add an audio buffer before the event loop
        audio_buffer = bytearray()
        while True:
            input("Press Enter to record and send audio (Ctrl+C to quit)...")
            audio_np = await record_audio()
            b64_audio = encode_audio(audio_np)
            media_msg = {
                "event": "media",
                "streamSid": "1234567890",
                "sequenceNumber": 1,
                "media": {"payload": b64_audio}
            }
            await websocket.send(json.dumps(media_msg))
            print("[Client] Audio sent. Waiting for response...")
            # Wait for response.audio.delta from server
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(data)

                if data.get("event") == "media":
                    # Buffer all audio chunks
                    audio_chunk = decode_audio(data["media"]["payload"])
                    # audio_buffer.extend(audio_chunk)
                    received_chunks.append(audio_chunk)
                elif data.get("event") == "mark":
                    print("[Client] AI finished speaking.")
                    # Play the buffered audio
                    # if audio_buffer:
                    #     play_audio(audio_buffer)
                    #     audio_buffer.clear()
                    if received_chunks:
                        full_audio = np.concatenate(received_chunks)
                        play_audio(full_audio)
                    break
                    break
                else:
                    print(f"[Client] Ignored event: {data.get('event')}")

if __name__ == "__main__":
    asyncio.run(main()) 