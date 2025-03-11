import pytest
from fastapi.testclient import TestClient
import os
from elevenlabs_scribe_mcp_server.main import app
import websockets
import asyncio
import json

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_transcribe_without_file():
    response = client.post("/transcribe")
    assert response.status_code == 422  # FastAPI validation error

def test_transcribe_with_invalid_file():
    files = {"audio_file": ("test.txt", b"not an audio file", "text/plain")}
    response = client.post("/transcribe", files=files)
    assert response.status_code == 500

@pytest.mark.asyncio
async def test_websocket_connection():
    async with websockets.connect("ws://localhost:8000/ws/transcribe") as websocket:
        # Send a small audio chunk
        await websocket.send(b"test audio data")
        
        try:
            # Try to receive a response with a timeout
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            assert "text" in data  # Assuming the response has a 'text' field
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for WebSocket response")
