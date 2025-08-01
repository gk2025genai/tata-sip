import asyncio
import websockets
import json
import base64
import sounddevice as sd
import numpy as np
import sys

SAMPLE_RATE = 8000  # Changed to 8kHz for u-law
CHANNELS = 1
DTYPE = 'int16'
CHUNK_DURATION = 2  # seconds to record per push-to-talk
received_chunks = []

def pcm16_to_ulaw(pcm16_array):
    """Convert PCM16 audio to u-law format"""
    # Normalize to [-1, 1]
    normalized = pcm16_array.astype(np.float32) / 32768.0
    
    # Apply u-law encoding
    ulaw_array = np.zeros_like(normalized, dtype=np.uint8)
    
    for i, sample in enumerate(normalized):
        # Clamp to [-1, 1]
        sample = np.clip(sample, -1.0, 1.0)
        
        # u-law encoding
        sign = 1 if sample >= 0 else 0
        sample = abs(sample)
        
        if sample < 1/255:
            ulaw_array[i] = 0
        else:
            # Find the segment
            segment = 1
            while segment < 8 and sample >= (1 << segment) / 256:
                segment += 1
            
            # Calculate quantization level
            quantization = int((sample * 256 / (1 << segment)) * 16)
            quantization = min(quantization, 15)
            
            # Combine sign, segment, and quantization
            ulaw_array[i] = (sign << 7) | ((8 - segment) << 4) | quantization
    
    return ulaw_array

def ulaw_to_pcm16(ulaw_array):
    """Convert u-law audio to PCM16 format"""
    # u-law decoding table
    ulaw_table = [
        -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
        -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
        -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
        -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
        -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
        -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
        -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
        -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
        -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
        -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
        -876, -844, -812, -780, -748, -716, -684, -652,
        -620, -588, -556, -524, -492, -460, -428, -396,
        -372, -356, -340, -324, -308, -292, -276, -260,
        -244, -228, -212, -196, -180, -164, -148, -132,
        -120, -112, -104, -96, -88, -80, -72, -64,
        -56, -48, -40, -32, -24, -16, -8, 0,
        32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
        23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
        15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
        11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
        7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
        5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
        3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
        2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
        1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
        1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
        876, 844, 812, 780, 748, 716, 684, 652,
        620, 588, 556, 524, 492, 460, 428, 396,
        372, 356, 340, 324, 308, 292, 276, 260,
        244, 228, 212, 196, 180, 164, 148, 132,
        120, 112, 104, 96, 88, 80, 72, 64,
        56, 48, 40, 32, 24, 16, 8, 0
    ]
    
    # Decode u-law to PCM16
    pcm16_array = np.array([ulaw_table[b] for b in ulaw_array], dtype=np.int16)
    
    return pcm16_array

async def record_audio(duration=CHUNK_DURATION):
    print(f"[Client] Recording for {duration} seconds...")
    audio = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
    sd.wait()
    return audio.flatten()

def encode_audio(audio_np):
    # Convert PCM16 to u-law
    ulaw_audio = pcm16_to_ulaw(audio_np)
    return base64.b64encode(ulaw_audio.tobytes()).decode('utf-8')

def decode_audio(b64_audio):
    audio_bytes = base64.b64decode(b64_audio)
    # Since OpenAI outputs G.711 u-law, we need to convert to PCM16 for playback
    ulaw_array = np.frombuffer(audio_bytes, dtype=np.uint8)
    pcm16_array = ulaw_to_pcm16(ulaw_array)
    return pcm16_array

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
                        received_chunks.clear()
                    break
                    break
                else:
                    print(f"[Client] Ignored event: {data.get('event')}")

if __name__ == "__main__":
    asyncio.run(main()) 