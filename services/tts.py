import audioop
from google.cloud import texttospeech

# Twilio expects 8 kHz mono mulaw audio
_SAMPLE_RATE = 8000

_client = texttospeech.TextToSpeechClient()

# Available Urdu (Pakistan) voices:
#   ur-PK-Standard-A  (female)
#   ur-PK-Standard-B  (male)
#   ur-PK-Wavenet-A   (female, more natural — billed separately)
#   ur-PK-Wavenet-B   (male,   more natural)
_VOICE = texttospeech.VoiceSelectionParams(
    language_code="ur-PK",
    name="ur-PK-Standard-A",
    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
)

_AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=_SAMPLE_RATE,
)


async def synthesize_speech(text: str) -> bytes:
    """
    Convert Urdu text → mulaw 8 kHz bytes ready to stream via Twilio.
    The Google TTS client is synchronous; we call it directly (it's fast
    enough that an executor is not necessary for typical response lengths).
    """
    if not text:
        return b""

    synthesis_input = texttospeech.SynthesisInput(text=text)

    try:
        response = _client.synthesize_speech(
            input=synthesis_input,
            voice=_VOICE,
            audio_config=_AUDIO_CONFIG,
        )
    except Exception as exc:
        print(f"[TTS] Google TTS error: {exc}")
        return b""

    # Google returns a WAV container; skip the 44-byte header to get raw PCM.
    pcm_data = response.audio_content[44:]

    # Convert 16-bit linear PCM → 8-bit mulaw (what Twilio Media Streams expect).
    mulaw_data = audioop.lin2ulaw(pcm_data, 2)
    return mulaw_data
