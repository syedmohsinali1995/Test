import asyncio
import audioop
import base64
import json
from fastapi import WebSocket, WebSocketDisconnect
from .stt import transcribe_audio, mulaw_to_pcm
from .tts import synthesize_speech
from .ai_agent import UrduAgent
from prompts.urdu_system import GREETING_TEXT

# ── Voice Activity Detection constants ───────────────────────────────────────
SILENCE_RMS_THRESHOLD = 400     # RMS below this = silence
SILENCE_SECONDS = 1.5           # seconds of silence before we process speech
SAMPLE_RATE = 8000
SAMPLE_WIDTH = 2                # bytes per sample (16-bit)
MIN_SPEECH_BYTES = SAMPLE_RATE * SAMPLE_WIDTH * 1  # at least 1 second of speech

# Chunk size for streaming audio back to Twilio (20 ms = 160 samples)
CHUNK_SIZE = 320


async def handle_websocket(websocket: WebSocket) -> None:
    """
    Main WebSocket handler for a Twilio Media Stream session.

    Flow per call:
      1. Twilio opens WebSocket → sends "start" event with streamSid.
      2. We greet the caller (TTS → audio).
      3. Receive mulaw audio frames → accumulate PCM → VAD.
      4. When silence detected after speech → Whisper STT.
      5. Claude generates Urdu reply → Google TTS → audio back to Twilio.
      6. Repeat until "stop" event or disconnect.
    """
    await websocket.accept()

    agent = UrduAgent()
    pcm_buffer = bytearray()
    silence_seconds = 0.0
    stream_sid: str = ""
    speaking = False

    try:
        async for raw_message in websocket.iter_text():
            data = json.loads(raw_message)
            event = data.get("event", "")

            # ── Call connected ────────────────────────────────────────────────
            if event == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"[WS] Stream started: {stream_sid}")
                await _send_speech(websocket, stream_sid, GREETING_TEXT)

            # ── Incoming audio frame ──────────────────────────────────────────
            elif event == "media":
                mulaw_bytes = base64.b64decode(data["media"]["payload"])
                pcm_chunk = mulaw_to_pcm(mulaw_bytes)
                rms = audioop.rms(pcm_chunk, SAMPLE_WIDTH)

                if rms > SILENCE_RMS_THRESHOLD:
                    # User is speaking
                    speaking = True
                    silence_seconds = 0.0
                    pcm_buffer.extend(pcm_chunk)
                else:
                    # Silence
                    chunk_duration = len(pcm_chunk) / (SAMPLE_RATE * SAMPLE_WIDTH)
                    silence_seconds += chunk_duration

                    if speaking:
                        pcm_buffer.extend(pcm_chunk)  # include trailing silence

                    # Enough silence after speech → process utterance
                    if (
                        speaking
                        and silence_seconds >= SILENCE_SECONDS
                        and len(pcm_buffer) >= MIN_SPEECH_BYTES
                    ):
                        speaking = False
                        audio_snapshot = bytes(pcm_buffer)
                        pcm_buffer.clear()
                        silence_seconds = 0.0

                        # Run STT + LLM + TTS concurrently where possible
                        transcript = await transcribe_audio(audio_snapshot)
                        print(f"[STT] '{transcript}'")

                        if transcript:
                            reply = await agent.get_response(transcript)
                            print(f"[Agent] '{reply}'")
                            await _send_speech(websocket, stream_sid, reply)

            # ── Call ended ────────────────────────────────────────────────────
            elif event == "stop":
                print(f"[WS] Stream stopped: {stream_sid}")
                break

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {stream_sid}")
    except Exception as exc:
        print(f"[WS] Unexpected error: {exc}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _send_speech(websocket: WebSocket, stream_sid: str, text: str) -> None:
    """Synthesize `text` to mulaw audio and stream it back to Twilio."""
    mulaw_audio = await synthesize_speech(text)
    if not mulaw_audio:
        return

    for i in range(0, len(mulaw_audio), CHUNK_SIZE):
        chunk = mulaw_audio[i : i + CHUNK_SIZE]
        payload = base64.b64encode(chunk).decode("utf-8")
        message = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload},
        }
        await websocket.send_text(json.dumps(message))
        await asyncio.sleep(0.02)   # 20 ms pacing to match real-time playback
