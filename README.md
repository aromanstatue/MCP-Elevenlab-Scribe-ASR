# ElevenLabs Scribe MCP Server

A Model Control Protocol (MCP) server implementation for ElevenLabs' Scribe speech-to-text API, providing real-time transcription capabilities with advanced context management and bidirectional streaming.

## Features

- **Real-time Transcription**: Stream audio directly from your microphone and get instant transcriptions
- **File-based Transcription**: Upload audio files for batch processing
- **MCP Protocol Support**: Full implementation of the Model Control Protocol for better context management
- **WebSocket Support**: Real-time bidirectional communication
- **Context Management**: Maintain conversation context for improved transcription accuracy
- **Multiple Audio Formats**: Support for various audio formats with automatic conversion
- **Language Detection**: Automatic language detection and confidence scoring
- **Event Detection**: Identify speech and non-speech audio events

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/elevenlabs-scribe-mcp-server.git
cd elevenlabs-scribe-mcp-server
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Create a `.env` file with your ElevenLabs API key:
```bash
ELEVENLABS_API_KEY=your-api-key-here
```

## Usage

### Starting the Server

```bash
python -m elevenlabs_scribe_mcp_server.main
```

The server will start on port 8000 by default (or the next available port).

### Using the Example Client

1. File Transcription:
```bash
python examples/client_example.py --file path/to/audio.wav
```

2. Microphone Transcription:
```bash
python examples/client_example.py --mic
```

### API Endpoints

1. REST API:
- `POST /transcribe`: Upload an audio file for transcription
- `GET /health`: Health check endpoint

2. WebSocket API:
- `ws://localhost:8000/ws/transcribe`: Real-time audio transcription

### MCP Protocol

The server implements the Model Control Protocol (MCP) with the following message types:

1. `INIT`: Initialize a new transcription session
2. `START`: Begin audio streaming
3. `AUDIO`: Send audio data
4. `TRANSCRIPTION`: Receive transcription results
5. `ERROR`: Error messages
6. `STOP`: End audio streaming
7. `DONE`: Complete session

## Development

### Running Tests

```bash
pytest tests/
```

### Project Structure

```
elevenlabs-scribe-mcp-server/
├── elevenlabs_scribe_mcp_server/
│   ├── __init__.py
│   ├── main.py              # FastAPI server
│   └── mcp/
│       ├── __init__.py
│       ├── protocol.py      # MCP protocol handler
│       ├── types.py         # Protocol types
│       └── elevenlabs.py    # ElevenLabs implementation
├── examples/
│   └── client_example.py    # Example client
├── tests/
│   └── test_transcribe.py   # Test suite
├── pyproject.toml           # Project metadata
└── README.md
```

## Requirements

- Python 3.8+
- FastAPI
- Uvicorn
- PyAudio (for microphone support)
- aiohttp
- python-dotenv
- pydantic

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- ElevenLabs for their excellent Scribe API
- FastAPI for the modern web framework
- The Python community for the amazing tools and libraries
