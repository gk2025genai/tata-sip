import asyncio
import websockets
import json
import base64
import sounddevice as sd
import numpy as np
import sys

SAMPLE_RATE = 8000
CHANNELS = 1
DURATION = 3  # seconds
MU = 255
received_chunks = []
def float_to_ulaw(audio):
    audio = np.clip(audio, -1.0, 1.0)
    magnitude = np.log1p(MU * np.abs(audio)) / np.log1p(MU)
    signal = np.sign(audio) * magnitude
    ulaw = ((signal + 1) / 2 * MU + 0.5).astype(np.uint8)
    return ulaw

def ulaw_to_float(ulaw):
    signal = 2 * (ulaw.astype(np.float32) / MU) - 1
    magnitude = (1 / MU) * ((1 + MU) ** np.abs(signal) - 1)
    return np.sign(signal) * magnitude

def record_audio():
    print(f"[Client] Recording {DURATION} seconds at 8000Hz...")
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32')
    sd.wait()
    return audio.flatten()

def encode_base64(ulaw_audio):
    return base64.b64encode(ulaw_audio.tobytes()).decode('utf-8')

def decode_base64(b64_audio):
    raw_bytes = base64.b64decode(b64_audio)
    return np.frombuffer(raw_bytes, dtype=np.uint8)

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
            # audio_np = await record_audio()
            # b64_audio = encode_audio(audio_np)

            float_audio = record_audio()
            ulaw_audio = float_to_ulaw(float_audio)
            # Base64 encode + decode
            b64_audio = encode_base64(ulaw_audio)

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

                if data.get("event") == "media":
                    # Buffer all audio chunks
                    audio_chunk = decode_base64(data["media"]["payload"])
                    # audio_buffer.extend(audio_chunk)
                    received_chunks.append(audio_chunk)
                elif data.get("event") == "mark":
                    print("[Client] AI finished speaking.")
                    if received_chunks:
                        ulaw_decoded = np.concatenate(received_chunks)
                        float_decoded = ulaw_to_float(ulaw_decoded)
                        play_audio(ulaw_decoded)
                    break
                else:
                    print(f"[Client] Ignored event: {data.get('event')}")

if __name__ == "__main__":
    asyncio.run(main()) 