import numpy as np
import sounddevice as sd
import asyncio
import sys
import os
from client_openai import pcm16_to_ulaw, ulaw_to_pcm16, play_audio, record_audio, encode_audio

SAMPLE_RATE = 8000  # Changed to 8kHz for u-law
CHANNELS = 1
DTYPE = 'int16'
CHUNK_DURATION = 2  # seconds to record per push-to-talk
ULAW_FILE = "output_ulaw.ulaw"


def save_ulaw_raw(file_path, ulaw_bytes):
    """Save raw ulaw bytes to file"""
    with open(file_path, "wb") as f:
        f.write(ulaw_bytes)
    print(f"[Client] Saved u-law audio to {file_path}")

def load_ulaw_raw(file_path):
    """Load raw ulaw bytes from file"""
    with open(file_path, "rb") as f:
        return f.read()

async def record_and_save():
    """Record audio and save as u-law file"""
    input("Press Enter to record audio (Ctrl+C to quit)...")
    audio_np = await record_audio()
    
    # Convert to u-law and save
    ulaw_data = pcm16_to_ulaw(audio_np)
    print("[Debug] Playing original audio...")
    play_audio(audio_np)
    
    print("[Debug] Playing u-law converted audio...")
    # Convert back to PCM16 for playback to test round-trip conversion
    converted_back = ulaw_to_pcm16(ulaw_data)
    play_audio(converted_back)
    save_ulaw_raw(ULAW_FILE, ulaw_data.tobytes())
    print(f"[Debug] Saved u-law data: {len(ulaw_data)} samples")


def play_saved_audio():
    """Load and play saved u-law audio file"""
    if not os.path.exists(ULAW_FILE):
        print(f"[Error] Audio file {ULAW_FILE} not found. Record audio first.")
        return
    
    print(f"[Client] Loading audio from {ULAW_FILE}")
    ulaw_bytes = load_ulaw_raw(ULAW_FILE)
    print(f"[Debug] Loaded {len(ulaw_bytes)} bytes from file")
    
    ulaw_array = np.frombuffer(ulaw_bytes, dtype=np.uint8)
    print(f"[Debug] Converted to u-law array: {len(ulaw_array)} samples")
    
    pcm16_array = ulaw_to_pcm16(ulaw_array)
    print(f"[Debug] Converted to PCM16: {len(pcm16_array)} samples")
    print("[Debug] Playing converted audio...")
    
    play_audio(pcm16_array)

async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "play":
        # Play mode
        play_saved_audio()
    else:
        # Record mode
        await record_and_save()

if __name__ == "__main__":
    asyncio.run(main()) 
