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
    """Convert PCM16 audio to u-law format using ITU-T G.711 standard"""
    # Constants for u-law encoding
    BIAS = 0x84
    CLIP = 32635
    
    def linear_to_ulaw(sample):
        """Convert a single PCM16 sample to u-law"""
        # Get sign and magnitude
        sign = 0x80 if sample < 0 else 0x00
        if sample < 0:
            sample = -sample
        
        # Clip the sample
        sample = min(sample, CLIP)
        
        # Add bias
        sample = sample + BIAS
        
        # Find the segment
        segment = 7
        for i in range(7):
            if sample <= (0xFF << i):
                segment = i
                break
        
        # Find quantization value
        quantization = (sample >> (segment + 3)) & 0x0F
        
        # Combine sign, segment, and quantization
        ulaw = sign | (segment << 4) | quantization
        
        # Complement for transmission
        return (~ulaw) & 0xFF
    
    # Apply u-law encoding to each sample
    ulaw_array = np.array([linear_to_ulaw(int(sample)) for sample in pcm16_array], dtype=np.uint8)
    
    return ulaw_array

def ulaw_to_pcm16(ulaw_array):
    """Convert u-law audio to PCM16 format using ITU-T G.711 standard"""
    # Constants for u-law decoding
    BIAS = 0x84
    
    def ulaw_to_linear(ulaw_byte):
        """Convert a single u-law byte to PCM16 sample"""
        # Complement the byte (undo transmission complement)
        ulaw_byte = (~ulaw_byte) & 0xFF
        
        # Extract sign, segment, and quantization
        sign = ulaw_byte & 0x80
        segment = (ulaw_byte >> 4) & 0x07
        quantization = ulaw_byte & 0x0F
        
        # Calculate linear value
        linear = (quantization << 3) + BIAS
        linear <<= segment
        
        # Subtract bias and apply sign
        linear -= BIAS
        if sign:
            linear = -linear
        
        # Clip to 16-bit range
        return max(-32768, min(32767, linear))
    
    # Apply u-law decoding to each byte
    pcm16_array = np.array([ulaw_to_linear(int(byte)) for byte in ulaw_array], dtype=np.int16)
    
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
    host = sys.argv[1] if len(sys.argv) > 1 else "ec2-3-86-47-105.compute-1.amazonaws.com"
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
            play_audio(audio_np)
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