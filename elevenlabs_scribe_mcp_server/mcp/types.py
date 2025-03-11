"""
MCP protocol types and data structures.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """MCP message types."""
    INIT = "init"
    START = "start"
    AUDIO = "audio"
    TRANSCRIPTION = "transcription"
    ERROR = "error"
    STOP = "stop"
    DONE = "done"


class AudioFormat(BaseModel):
    """Audio format configuration."""
    sample_rate: int = Field(default=16000, description="Sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    sample_width: int = Field(default=2, description="Sample width in bytes")
    encoding: str = Field(default="pcm", description="Audio encoding format")


class TranscriptionConfig(BaseModel):
    """Transcription configuration."""
    model_id: str = Field(default="scribe_v1", description="Model ID to use for transcription")
    language: Optional[str] = Field(default=None, description="Target language code")
    max_context_length: Optional[int] = Field(default=1000, description="Maximum context length in tokens")
    detect_language: bool = Field(default=True, description="Whether to detect language")
    detect_events: bool = Field(default=True, description="Whether to detect audio events")


class Word(BaseModel):
    """Word-level transcription result."""
    text: str = Field(..., description="Transcribed text")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    type: str = Field(default="speech", description="Word type (speech, event, etc.)")


class TranscriptionResult(BaseModel):
    """Transcription result."""
    text: str = Field(..., description="Transcribed text")
    language_code: Optional[str] = Field(default=None, description="Detected language code")
    language_probability: Optional[float] = Field(default=None, description="Language detection confidence")
    words: List[Word] = Field(default_factory=list, description="Word-level results")


class MCPError(BaseModel):
    """MCP error message."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


class MCPMessage(BaseModel):
    """Base MCP message."""
    type: MessageType = Field(..., description="Message type")
    session_id: str = Field(..., description="Session ID")
    sequence: int = Field(..., description="Message sequence number")
    timestamp: float = Field(..., description="Message timestamp")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Message payload")
