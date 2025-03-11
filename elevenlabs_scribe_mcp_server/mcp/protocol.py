"""
MCP protocol handler implementation.
"""
import asyncio
import json
import time
import uuid
from typing import Optional, Dict, Any, AsyncGenerator
from .types import (
    MessageType,
    AudioFormat,
    TranscriptionConfig,
    TranscriptionResult,
    MCPMessage,
    MCPError,
)


class MCPSession:
    """Manages a single MCP session for speech-to-text."""
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        audio_format: Optional[AudioFormat] = None,
        config: Optional[TranscriptionConfig] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.audio_format = audio_format or AudioFormat()
        self.config = config or TranscriptionConfig()
        self.sequence = 0
        self.start_time = time.time()
        self.context_buffer = []
        self.is_active = True
        self._audio_queue = asyncio.Queue()
        self._result_queue = asyncio.Queue()
        
    def create_message(
        self,
        type: MessageType,
        payload: Optional[Dict[str, Any]] = None
    ) -> MCPMessage:
        """Create a new MCP message."""
        msg = MCPMessage(
            type=type,
            session_id=self.session_id,
            sequence=self.sequence,
            timestamp=time.time() - self.start_time,
            payload=payload
        )
        self.sequence += 1
        return msg
        
    async def push_audio(self, audio_data: bytes) -> None:
        """Push audio data to the processing queue."""
        await self._audio_queue.put(audio_data)
        
    async def get_audio(self) -> AsyncGenerator[bytes, None]:
        """Get audio data from the queue."""
        while self.is_active:
            try:
                audio_data = await self._audio_queue.get()
                yield audio_data
            except asyncio.CancelledError:
                break
                
    async def push_result(self, result: TranscriptionResult) -> None:
        """Push transcription result."""
        await self._result_queue.put(result)
        
    async def get_result(self) -> AsyncGenerator[TranscriptionResult, None]:
        """Get transcription results."""
        while self.is_active:
            try:
                result = await self._result_queue.get()
                yield result
            except asyncio.CancelledError:
                break
                
    def update_context(self, text: str) -> None:
        """Update context buffer with new text."""
        self.context_buffer.append(text)
        if self.config.max_context_length:
            # Simple token-based truncation
            total_tokens = sum(len(t.split()) for t in self.context_buffer)
            while total_tokens > self.config.max_context_length:
                removed = self.context_buffer.pop(0)
                total_tokens -= len(removed.split())
                
    def get_context(self) -> str:
        """Get current context."""
        return " ".join(self.context_buffer)
        
    async def close(self) -> None:
        """Close the session."""
        self.is_active = False
        # Cancel any pending tasks
        self._audio_queue = asyncio.Queue()
        self._result_queue = asyncio.Queue()


class MCPProtocolHandler:
    """Handles MCP protocol messages and session management."""
    
    def __init__(self):
        self.sessions: Dict[str, MCPSession] = {}
        
    async def handle_message(self, message: MCPMessage) -> MCPMessage:
        """Handle incoming MCP message."""
        try:
            if message.type == MessageType.INIT:
                return await self._handle_init(message)
            elif message.type == MessageType.START:
                return await self._handle_start(message)
            elif message.type == MessageType.AUDIO:
                return await self._handle_audio(message)
            elif message.type == MessageType.STOP:
                return await self._handle_stop(message)
            else:
                raise ValueError(f"Unsupported message type: {message.type}")
                
        except Exception as e:
            return MCPMessage(
                type=MessageType.ERROR,
                session_id=message.session_id,
                sequence=message.sequence,
                timestamp=time.time(),
                payload=MCPError(
                    code="protocol_error",
                    message=str(e)
                ).dict()
            )
            
    async def _handle_init(self, message: MCPMessage) -> MCPMessage:
        """Handle session initialization."""
        payload = message.payload or {}
        session = MCPSession(
            session_id=message.session_id,
            audio_format=AudioFormat(**payload.get("audio_format", {})),
            config=TranscriptionConfig(**payload.get("config", {}))
        )
        self.sessions[session.session_id] = session
        return session.create_message(
            MessageType.INIT,
            payload={"status": "ready"}
        )
        
    async def _handle_start(self, message: MCPMessage) -> MCPMessage:
        """Handle transcription start."""
        session = self.sessions.get(message.session_id)
        if not session:
            raise ValueError(f"Session not found: {message.session_id}")
            
        return session.create_message(
            MessageType.START,
            payload={"status": "started"}
        )
        
    async def _handle_audio(self, message: MCPMessage) -> MCPMessage:
        """Handle audio data."""
        session = self.sessions.get(message.session_id)
        if not session:
            raise ValueError(f"Session not found: {message.session_id}")
            
        if not message.payload or "data" not in message.payload:
            raise ValueError("Audio data missing in payload")
            
        await session.push_audio(message.payload["data"])
        return session.create_message(
            MessageType.AUDIO,
            payload={"status": "received"}
        )
        
    async def _handle_stop(self, message: MCPMessage) -> MCPMessage:
        """Handle session stop."""
        session = self.sessions.get(message.session_id)
        if not session:
            raise ValueError(f"Session not found: {message.session_id}")
            
        await session.close()
        del self.sessions[message.session_id]
        return session.create_message(
            MessageType.STOP,
            payload={"status": "stopped"}
        )
        
    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)
