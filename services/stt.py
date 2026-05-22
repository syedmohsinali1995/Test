import io
import wave
import audioop
from openai import AsyncOpenAI
from config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)

SAMPLE_RATE = 8000      # Twilio sends 8kHz mulaw audio
SAMPLE_WIDTH = 2        # 16-bit PCM after decoding


async def transcribe_audio(pcm_data: bytes) -> str:
    """
    Transcribe raw 16-bit PCM audio (8 kHz mono) to Urdu text via Whisper.
    Returns an empty string if the audio is too short or transcription fails.
    """
    if len(pcm_data) < SAMPLE_RATE * SAMPLE_WIDTH:   # less than 1 second
        return ""

    wav_bytes = _pcm_to_wav(pcm_data)

    try:
        response = await _client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_bytes, "audio/wav"),
            language="ur",
        )
        text = response.text.strip()
        return text
    except Exception as exc:
        print(f"[STT] Whisper error: {exc}")
        return ""


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw PCM bytes in a valid WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def mulaw_to_pcm(mulaw_bytes: bytes) -> bytes:
    """Convert 8-bit mulaw bytes (from Twilio) to 16-bit linear PCM."""
    return audioop.ulaw2lin(mulaw_bytes, SAMPLE_WIDTH)
