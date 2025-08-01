# Tata SIP Socket v2 - G.711 u-law Audio Support

This project implements a real-time audio conversation system using WebSocket connections and OpenAI's real-time API. The system has been updated to support G.711 u-law audio format at 8kHz sample rate.

## Features

- **G.711 u-law Audio Format**: Supports u-law encoding/decoding for efficient audio transmission
- **8kHz Sample Rate**: Optimized for telephony applications
- **Real-time Conversation**: Uses OpenAI's real-time API for live audio conversations
- **WebSocket Communication**: Client-server communication via WebSocket protocol
- **Function Calling**: Supports OpenAI function calls (weather, notepad)
- **Secure Configuration**: Uses .env file for API key management

## Audio Format Changes

### Previous Format
- **Input/Output**: PCM16 at 24kHz
- **Bit Depth**: 16-bit
- **Sample Rate**: 24,000 Hz

### New Format
- **Input/Output**: G.711 u-law at 8kHz
- **Bit Depth**: 8-bit (compressed)
- **Sample Rate**: 8,000 Hz
- **Compression**: u-law encoding for efficient bandwidth usage

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your OpenAI API key:
   - Copy `.env.example` to `.env`
   - Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```
   - Get your API key from: https://platform.openai.com/api-keys

## Usage

### Starting the Server

```bash
python server_openai.py
```

The server will start on port 8766 by default.

### Running the Client

```bash
python client_openai.py [host] [port]
```

Example:
```bash
python client_openai.py localhost 8766
```

### Testing u-law Conversion

To test the u-law audio conversion:

```bash
python test_ulaw.py
```

This will play a test tone to verify the conversion is working correctly.

## Audio Processing Flow

1. **Client Recording**: Records audio at 8kHz PCM16
2. **u-law Encoding**: Converts PCM16 to u-law format
3. **Transmission**: Sends u-law audio via WebSocket
4. **Server Processing**: Receives u-law audio and forwards to OpenAI
5. **OpenAI Processing**: OpenAI processes u-law audio directly
6. **Response**: OpenAI returns u-law audio
7. **Client Playback**: Converts u-law back to PCM16 for playback

## File Structure

- `server_openai.py`: WebSocket server implementation
- `client_openai.py`: WebSocket client with audio recording/playback
- `openai_handler.py`: OpenAI API integration and audio processing
- `test_ulaw.py`: Test script for u-law conversion
- `requirements.txt`: Python dependencies
- `.env`: Environment variables (API key) - **DO NOT COMMIT**
- `.env.example`: Example environment file
- `.gitignore`: Git ignore rules

## Audio Conversion Functions

### PCM16 to u-law
```python
def pcm16_to_ulaw(pcm16_array):
    # Converts 16-bit PCM to 8-bit u-law
```

### u-law to PCM16
```python
def ulaw_to_pcm16(ulaw_array):
    # Converts 8-bit u-law to 16-bit PCM
```

## Benefits of u-law Format

1. **Bandwidth Efficiency**: 8-bit vs 16-bit reduces bandwidth by 50%
2. **Telephony Standard**: Widely used in telephony systems
3. **OpenAI Compatibility**: OpenAI supports u-law format natively
4. **Quality**: Good quality for speech at 8kHz

## Security

- **API Key Protection**: API keys are stored in `.env` file (not committed to git)
- **Environment Variables**: Uses python-dotenv for secure configuration
- **Git Ignore**: `.env` file is excluded from version control

## Troubleshooting

### Audio Quality Issues
- Ensure microphone supports 8kHz recording
- Check audio drivers and settings
- Verify u-law conversion is working with test script

### Connection Issues
- Check OpenAI API key is valid in `.env` file
- Verify network connectivity
- Ensure WebSocket server is running

### Environment Issues
- Make sure `.env` file exists and contains `OPENAI_API_KEY`
- Check that python-dotenv is installed
- Verify API key format is correct

### Performance Issues
- u-law format reduces bandwidth usage
- 8kHz sample rate reduces processing load
- Consider adjusting chunk duration for better latency

## API Configuration

The OpenAI session is configured with:
- **Input Format**: `g711_ulaw`
- **Output Format**: `g711_ulaw`
- **Sample Rate**: 8kHz (implicit)
- **Voice**: `alloy`
- **Temperature**: 1.0

## Function Support

The system supports OpenAI function calls:
- `get_weather(city)`: Get weather information
- `write_notepad(content, date)`: Write to notepad

## License

This project is for educational and development purposes. 