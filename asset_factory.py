import os
import json
import asyncio
import aiohttp
import aiofiles
from tenacity import retry, stop_after_attempt, wait_exponential
import whisper_timestamped as whisper
from typing import List, Dict, Any

class AssetFactory:
    def __init__(self, runware_api_key: str, elevenlabs_api_key: str):
        self.runware_api_key = runware_api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        # Ensure Whisper model is loaded lazily or on init
        self.whisper_model = None

    def _get_whisper_model(self):
        if self.whisper_model is None:
            self.whisper_model = whisper.load_model("base") # Use small/base for speed locally
        return self.whisper_model

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_image(self, session: aiohttp.ClientSession, prompt: str, output_path: str):
        """Asynchronously calls Runware API to generate an image."""
        if os.path.exists(output_path):
            print(f"Skipping {output_path}, already exists.")
            return output_path

        url = "https://api.runware.ai/v1" # Mock or actual endpoint
        headers = {"Authorization": f"Bearer {self.runware_api_key}", "Content-Type": "application/json"}
        # Assume Runware accepts a payload like this (adjust to real API specs)
        payload = [
            {
                "taskType": "imageInference",
                "taskUUID": "uuid-here", # Often required, can generate dynamically
                "positivePrompt": prompt,
                "width": 512,
                "height": 896, # ~9:16 aspect ratio
            }
        ]

        # For the sake of the orchestrator, we might mock the actual call if API key is not present,
        # but here we implement the intended logic.
        # We will simulate a successful download or mock it in tests.

        if self.runware_api_key == "MOCK_KEY":
            # Mock behavior for testing
            await asyncio.sleep(0.1)
            async with aiofiles.open(output_path, "wb") as f:
                await f.write(b"mock_image_data")
            return output_path

        async with session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
            data = await response.json()
            # Extract image URL from response (assuming standard structure)
            if data and "data" in data and len(data["data"]) > 0:
                image_url = data["data"][0].get("imageURL")
                if image_url:
                    async with session.get(image_url) as img_resp:
                        img_resp.raise_for_status()
                        async with aiofiles.open(output_path, "wb") as f:
                            await f.write(await img_resp.read())
                        return output_path
            raise Exception("Failed to get imageURL from Runware")

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_audio(self, session: aiohttp.ClientSession, text: str, output_path: str):
        """Asynchronously calls ElevenLabs API to generate TTS audio."""
        if os.path.exists(output_path):
            print(f"Skipping {output_path}, already exists.")
            return output_path

        voice_id = "21m00Tcm4TlvDq8ikWAM" # Example generic voice
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        if self.elevenlabs_api_key == "MOCK_KEY":
            await asyncio.sleep(0.1)
            async with aiofiles.open(output_path, "wb") as f:
                await f.write(b"mock_audio_data")
            return output_path

        async with session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async with aiofiles.open(output_path, "wb") as f:
                await f.write(await response.read())
            return output_path

    def _transcribe_audio(self, audio_path: str, output_json_path: str):
        """Passes audio through whisper-timestamped to get word-level boundaries."""
        if os.path.exists(output_json_path):
            print(f"Skipping transcription {output_json_path}, already exists.")
            return output_json_path

        model = self._get_whisper_model()
        audio = whisper.load_audio(audio_path)
        result = whisper.transcribe(model, audio, language="en")

        words_data = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                words_data.append({
                    "word": word["text"],
                    "start_time": word["start"],
                    "end_time": word["end"]
                })

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(words_data, f, indent=4)

        return output_json_path

    async def generate_assets(self, episode_id: str, compiled_prompts: List[Dict[str, Any]], script_text: str):
        """Main orchestrator for Module 2."""
        base_dir = f"./assets/ep_{episode_id}"
        img_dir = os.path.join(base_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        audio_path = os.path.join(base_dir, "audio.mp3")
        transcription_path = os.path.join(base_dir, "transcription.json")

        async with aiohttp.ClientSession() as session:
            # 1. Start audio generation and transcription
            # Transcribe depends on audio, so we wrap it
            async def process_audio_and_transcribe():
                await self._generate_audio(session, script_text, audio_path)
                # whisper-timestamped is synchronous, run in thread pool
                loop = asyncio.get_event_loop()
                if self.elevenlabs_api_key != "MOCK_KEY": # Don't transcribe mock audio
                    await loop.run_in_executor(None, self._transcribe_audio, audio_path, transcription_path)
                else:
                    # Mock transcription
                    with open(transcription_path, "w") as f:
                        json.dump([{"word": "Hello", "start_time": 0.0, "end_time": 0.5}], f)

            # 2. Start image generation tasks
            image_tasks = []
            for prompt_data in compiled_prompts:
                panel_id = prompt_data["panel_id"]
                prompt = prompt_data["prompt"]
                output_path = os.path.join(img_dir, f"panel_{panel_id:03d}.png")
                task = self._generate_image(session, prompt, output_path)
                image_tasks.append(task)

            # 3. Run all concurrently
            await asyncio.gather(process_audio_and_transcribe(), *image_tasks)

        return {
            "image_dir": img_dir,
            "audio_path": audio_path,
            "transcription_path": transcription_path
        }
