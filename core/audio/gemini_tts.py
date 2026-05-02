import os
import struct
import asyncio
import mimetypes
from pathlib import Path

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from core.audio.base import BaseAudioGenerator
from config import settings
from logger import logger


class GeminiTTSProvider(BaseAudioGenerator):
    """Uses Google Gemini 3.1 Flash Audio Modality for expressive manhwa narration."""

    def __init__(self):
        project = settings.GOOGLE_CLOUD_PROJECT
        location = settings.GOOGLE_CLOUD_LOCATION
        credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS

        if credentials_path and Path(credentials_path).exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        if project:
            self.client = genai.Client(
                vertexai=True, project=project, location=location
            )
        else:
            raise ValueError("No GOOGLE_CLOUD_PROJECT found in settings.")

    @retry(
        stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_audio(self, text: str, output_path: str) -> str:
        path = Path(output_path)
        if path.exists():
            logger.info("Skipping %s, already exists.", path)
            return str(path)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._generate_sync, text, output_path)
        return str(path)

    def _generate_sync(self, text: str, output_path: str):
        model = "gemini-3.1-flash-tts-preview"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"""Read the following transcript based on the audio profile and director's note.

# Audio Profile
A dynamic, punchy anime recap narrator voice — high energy, gripping, and cinematic. Delivers each line with urgency and excitement, like recapping a major manga/manhwa arc. Uses natural dramatic pauses before big reveals, and speeds up slightly when tension is building.

# Director's note
Style: Hype, bold, authoritative. Like a YouTube anime recap channel. Tone: Dramatic but clear. Pace: Varied — quick bursts for action moments, deliberate slow-down for emotional or shocking beats. Accent: Neutral American. No over-acting, stay controlled and cinematic.

## Transcript:
{text}"""
                    ),
                ],
            ),
        ]

        config = types.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Fenrir")
                )
            ),
        )

        response = self.client.models.generate_content(
            model=model, contents=contents, config=config
        )

        if (
            not response.parts
            or not response.parts[0].inline_data
            or not response.parts[0].inline_data.data
        ):
            raise RuntimeError("Gemini did not return any audio data.")

        inline_data = response.parts[0].inline_data
        data_buffer = inline_data.data

        if mimetypes.guess_extension(inline_data.mime_type) is None:
            data_buffer = self._convert_to_wav(data_buffer, inline_data.mime_type)

        with open(output_path, "wb") as f:
            f.write(data_buffer)

    def _convert_to_wav(self, audio_data: bytes, mime_type: str) -> bytes:
        parameters = self._parse_audio_mime_type(mime_type)
        bits_per_sample = parameters["bits_per_sample"]
        sample_rate = parameters["rate"]
        num_channels = 1
        data_size = len(audio_data)
        bytes_per_sample = bits_per_sample // 8
        block_align = num_channels * bytes_per_sample
        byte_rate = sample_rate * block_align
        chunk_size = 36 + data_size

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            chunk_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            data_size,
        )
        return header + audio_data

    def _parse_audio_mime_type(self, mime_type: str) -> dict:
        bits_per_sample = 16
        rate = 24000
        for param in mime_type.split(";"):
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate = int(param.split("=", 1)[1])
                except Exception:
                    pass
            elif param.startswith("audio/L"):
                try:
                    bits_per_sample = int(param.split("L", 1)[1])
                except Exception:
                    pass
        return {"bits_per_sample": bits_per_sample, "rate": rate}
