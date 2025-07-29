import numpy as np
import sounddevice as sd
import base64

SAMPLE_RATE = 8000
CHANNELS = 1
DURATION = 3  # seconds
MU = 255

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

def record_and_play():
    float_audio = record_audio()
    ulaw_audio = float_to_ulaw(float_audio)

    # Base64 encode + decode
    b64_audio = encode_base64(ulaw_audio)
    print("[Client] Audio encoded to base64")

    ulaw_decoded = decode_base64(b64_audio)
    print("[Client] Audio decoded from base64, now playing...")

    float_decoded = ulaw_to_float(ulaw_decoded)
    sd.play(float_decoded, samplerate=SAMPLE_RATE)
    sd.wait()

if __name__ == "__main__":
    record_and_play()
