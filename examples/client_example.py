import asyncio
import websockets
import requests
from pathlib import Path
import sys
import argparse
import wave
import pyaudio
import json
import time
import numpy as np
import uuid

class ScribeClient:
    def __init__(self, server_url: str = None):
        if server_url is None:
            # Try to find the server port by checking health endpoint on common ports
            self.server_url = self._find_server()
        else:
            self.server_url = server_url
            
        if not self.server_url:
            raise RuntimeError("Could not find running Scribe server")
            
        self.ws_url = self.server_url.replace("http", "ws")
        print(f"Connected to Scribe server at {self.server_url}")
        
    def _find_server(self) -> str:
        """Find the running server by checking common ports."""
        for port in range(8000, 8100):
            try:
                url = f"http://localhost:{port}"
                response = requests.get(f"{url}/health")
                if response.status_code == 200:
                    return url
            except requests.exceptions.ConnectionError:
                continue
        return None
        
    def transcribe_file(self, audio_path: str) -> dict:
        """
        Transcribe an audio file using the REST API.
        """
        with open(audio_path, 'rb') as f:
            files = {'audio_file': f}
            response = requests.post(f"{self.server_url}/transcribe", files=files)
            response.raise_for_status()
            return response.json()

    async def transcribe_microphone(self):
        """
        Transcribe audio from microphone in real-time using WebSocket and MCP protocol.
        """
        # Audio recording parameters
        CHUNK = 4096  # Increased chunk size for better streaming
        FORMAT = pyaudio.paFloat32
        CHANNELS = 1
        RATE = 16000  # Required rate for ElevenLabs API
        
        p = pyaudio.PyAudio()
        
        # Open audio stream
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        print("Connecting to WebSocket...")
        async with websockets.connect(f"{self.ws_url}/ws/transcribe") as websocket:
            print("Connected! Recording... Press Ctrl+C to stop.")
            print("Speak into your microphone...")
            
            try:
                # Buffer to accumulate audio data
                audio_buffer = bytearray()
                last_send_time = time.time()
                sequence = 0
                session_id = str(uuid.uuid4())
                
                while True:
                    # Read audio chunk as float32
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    
                    # Convert float32 to int16 (required by ElevenLabs API)
                    audio_array = np.frombuffer(data, dtype=np.float32)
                    audio_array = (audio_array * 32767).astype(np.int16)
                    audio_buffer.extend(audio_array.tobytes())
                    
                    # Send accumulated data every 2 seconds
                    current_time = time.time()
                    if current_time - last_send_time >= 2.0:
                        if audio_buffer:
                            # Send audio data
                            await websocket.send_bytes(bytes(audio_buffer))
                            audio_buffer.clear()
                            last_send_time = current_time
                            sequence += 1
                            
                            # Get transcription
                            try:
                                response = await websocket.recv()
                                result = json.loads(response)
                                if result.get('text'):
                                    print(f"\nTranscription: {result['text']}\n")
                                    print("Speak into your microphone...")
                                elif result.get('error'):
                                    print(f"\nError: {result['error']}\n")
                            except websockets.exceptions.ConnectionClosed:
                                print("Connection closed by server")
                                break
                    
            except KeyboardInterrupt:
                print("\nStopping recording...")
            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()

def main():
    parser = argparse.ArgumentParser(description="ElevenLabs Scribe Client Example")
    parser.add_argument("--server", help="Server URL (optional, will auto-detect if not provided)")
    parser.add_argument("--file", help="Audio file to transcribe")
    parser.add_argument("--mic", action="store_true", help="Use microphone input")
    
    args = parser.parse_args()
    
    try:
        client = ScribeClient(args.server)
        
        if args.file:
            try:
                result = client.transcribe_file(args.file)
                print(f"Transcription: {result['text']}")
            except Exception as e:
                print(f"Error transcribing file: {e}")
                sys.exit(1)
        
        elif args.mic:
            try:
                asyncio.run(client.transcribe_microphone())
            except Exception as e:
                print(f"Error with microphone transcription: {e}")
                sys.exit(1)
        
        else:
            parser.print_help()
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
