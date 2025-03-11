from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import logging
import time
import socket
from typing import Dict, Any
from .mcp.types import (
    MessageType,
    AudioFormat,
    TranscriptionConfig,
    MCPMessage,
    MCPError,
)
from .mcp.protocol import MCPProtocolHandler
from .mcp.elevenlabs import ElevenLabsTranscriptionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="ElevenLabs Scribe MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP components
protocol_handler = MCPProtocolHandler()
transcription_service = ElevenLabsTranscriptionService()

def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

@app.post("/transcribe")
async def transcribe_endpoint(audio_file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    REST endpoint for file transcription using MCP protocol.
    """
    try:
        # Create a new MCP session
        session = protocol_handler.sessions.get("file_upload") or \
                 (await protocol_handler.handle_message(MCPMessage(
                     type=MessageType.INIT,
                     session_id="file_upload",
                     sequence=0,
                     timestamp=time.time(),
                     payload={
                         "audio_format": AudioFormat().dict(),
                         "config": TranscriptionConfig().dict()
                     }
                 ))).session_id

        # Read file content
        content = await audio_file.read()

        # Send audio through MCP protocol
        audio_message = MCPMessage(
            type=MessageType.AUDIO,
            session_id=session,
            sequence=1,
            timestamp=time.time(),
            payload={"data": content}
        )
        await protocol_handler.handle_message(audio_message)

        # Get first result
        result = None
        async for r in protocol_handler.get_session(session).get_result():
            result = r
            break

        # Stop session
        await protocol_handler.handle_message(MCPMessage(
            type=MessageType.STOP,
            session_id=session,
            sequence=2,
            timestamp=time.time()
        ))

        return result.dict() if result else {"error": "No transcription result"}

    except Exception as e:
        logger.error(f"Error processing audio file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transcription using MCP protocol.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        # Initialize MCP session
        init_message = MCPMessage(
            type=MessageType.INIT,
            session_id=str(time.time()),
            sequence=0,
            timestamp=time.time(),
            payload={
                "audio_format": AudioFormat().dict(),
                "config": TranscriptionConfig().dict()
            }
        )
        response = await protocol_handler.handle_message(init_message)
        session = protocol_handler.get_session(response.session_id)

        # Start transcription
        await protocol_handler.handle_message(MCPMessage(
            type=MessageType.START,
            session_id=session.session_id,
            sequence=1,
            timestamp=time.time()
        ))

        # Start the transcription service
        await transcription_service.start_session(session)

        try:
            # Handle incoming audio data
            while True:
                try:
                    data = await websocket.receive_bytes()
                except WebSocketDisconnect:
                    break

                # Send audio through MCP protocol
                await protocol_handler.handle_message(MCPMessage(
                    type=MessageType.AUDIO,
                    session_id=session.session_id,
                    sequence=session.sequence,
                    timestamp=time.time(),
                    payload={"data": data}
                ))

                # Send any available results
                async for result in session.get_result():
                    await websocket.send_json(result.dict())

        finally:
            # Stop session
            await protocol_handler.handle_message(MCPMessage(
                type=MessageType.STOP,
                session_id=session.session_id,
                sequence=session.sequence,
                timestamp=time.time()
            ))
            await transcription_service.stop_session(session.session_id)

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = find_available_port()
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
