"""
ElevenLabs-specific MCP implementation.
"""
import os
import asyncio
import aiohttp
import wave
import tempfile
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from dotenv import load_dotenv
from .types import (
    TranscriptionConfig,
    TranscriptionResult,
    Word,
)
from .protocol import MCPSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ElevenLabsProvider:
    """ElevenLabs speech-to-text provider implementation."""
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is not set")
            
        self.api_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "xi-api-key": self.api_key,
            "accept": "application/json",
        }
        
    async def process_stream(
        self,
        session: MCPSession
    ) -> AsyncGenerator[TranscriptionResult, None]:
        """Process audio stream and yield transcription results."""
        async with aiohttp.ClientSession() as http_session:
            async for audio_chunk in session.get_audio():
                if not audio_chunk:
                    continue
                    
                try:
                    # Convert audio chunk to WAV
                    wav_data = await self._convert_to_wav(
                        audio_chunk,
                        session.audio_format
                    )
                    
                    # Send to ElevenLabs API
                    result = await self._transcribe(
                        http_session,
                        wav_data,
                        session.config
                    )
                    
                    # Update context if needed
                    if result.text:
                        session.update_context(result.text)
                    
                    yield result
                    
                except Exception as e:
                    logger.error(f"Error processing audio chunk: {e}")
                    continue
    
    async def _convert_to_wav(
        self,
        audio_data: bytes,
        audio_format: Any
    ) -> bytes:
        """Convert audio data to WAV format."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            try:
                with wave.open(temp_wav.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(16000)  # 16kHz
                    wav_file.writeframes(audio_data)
                
                with open(temp_wav.name, 'rb') as f:
                    return f.read()
            finally:
                try:
                    os.unlink(temp_wav.name)
                except:
                    pass
    
    async def _transcribe(
        self,
        session: aiohttp.ClientSession,
        wav_data: bytes,
        config: TranscriptionConfig
    ) -> TranscriptionResult:
        """Send audio to ElevenLabs API for transcription."""
        url = f"{self.api_url}/speech-to-text"
        
        # Prepare form data
        data = aiohttp.FormData()
        data.add_field(
            'file',
            wav_data,
            filename='audio.wav',
            content_type='audio/wav'
        )
        data.add_field('model_id', config.model_id)
        
        if config.language:
            data.add_field('language', config.language)
        
        async with session.post(url, headers=self.headers, data=data) as response:
            response_text = await response.text()
            logger.info(f"Response status: {response.status}")
            logger.info(f"Response body: {response_text}")
            
            if response.status != 200:
                raise Exception(f"ElevenLabs API error: {response_text}")
            
            result = await response.json()
            
            # Convert to our TranscriptionResult format
            return TranscriptionResult(
                text=result["text"],
                language_code=result["language_code"],
                language_probability=result["language_probability"],
                words=[
                    Word(
                        text=w["text"],
                        start=w["start"],
                        end=w["end"],
                        type=w.get("type", "speech")
                    )
                    for w in result.get("words", [])
                ]
            )


class ElevenLabsTranscriptionService:
    """Service that manages ElevenLabs transcription sessions."""
    
    def __init__(self):
        self.provider = ElevenLabsProvider()
        self._tasks: Dict[str, asyncio.Task] = {}
        
    async def start_session(self, session: MCPSession) -> None:
        """Start processing for a session."""
        if session.session_id in self._tasks:
            raise ValueError(f"Session already running: {session.session_id}")
        
        # Create task for processing audio stream
        task = asyncio.create_task(self._process_session(session))
        self._tasks[session.session_id] = task
        
    async def stop_session(self, session_id: str) -> None:
        """Stop processing for a session."""
        task = self._tasks.pop(session_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
    async def _process_session(self, session: MCPSession) -> None:
        """Process audio stream and handle results."""
        try:
            async for result in self.provider.process_stream(session):
                await session.push_result(result)
        except asyncio.CancelledError:
            logger.info(f"Session cancelled: {session.session_id}")
        except Exception as e:
            logger.error(f"Session error: {e}")
        finally:
            await session.close()
