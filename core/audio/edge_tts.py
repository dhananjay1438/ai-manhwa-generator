import edge_tts
from core.audio.base import BaseAudioGenerator


class EdgeTTSProvider(BaseAudioGenerator):
    """Uses Microsoft Edge TTS (Free, high quality but can be monotonous)."""

    async def generate_audio(
        self, text: str, output_path: str, voice: str = "en-GB-RyanNeural"
    ):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path
