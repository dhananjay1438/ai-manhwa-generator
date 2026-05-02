import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

import aiofiles
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from logger import logger


class BaseImageGenerator(ABC):
    @abstractmethod
    async def generate_image(self, prompt: str, output_path: str) -> str:
        pass


class BaseAudioGenerator(ABC):
    @abstractmethod
    async def generate_audio(self, text: str, output_path: str) -> str:
        pass


class RunwareImageGenerator(BaseImageGenerator):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_image(self, prompt: str, output_path: str) -> str:
        path = Path(output_path)
        if path.exists():
            logger.info("Skipping %s, already exists.", path)
            return str(path)

        if self.api_key == "MOCK_KEY":
            await asyncio.sleep(0.1)
            async with aiofiles.open(path, "wb") as f:
                await f.write(b"mock_image_data")
            return str(path)

        async with aiohttp.ClientSession() as session:
            url = "https://api.runware.ai/v1"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = [
                {
                    "taskType": "imageInference",
                    "taskUUID": "uuid-here",
                    "positivePrompt": prompt,
                    "width": 512,
                    "height": 896,
                }
            ]
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                if data and "data" in data and len(data["data"]) > 0:
                    image_url = data["data"][0].get("imageURL")
                    if image_url:
                        async with session.get(image_url) as img_resp:
                            img_resp.raise_for_status()
                            async with aiofiles.open(path, "wb") as f:
                                await f.write(await img_resp.read())
                            return str(path)
                raise Exception("Failed to get imageURL from Runware")


class VertexAITTSGenerator(BaseAudioGenerator):
    def __init__(self, api_key: str, voice: str):
        self.api_key = api_key
        self.voice = voice

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_audio(self, text: str, output_path: str) -> str:
        path = Path(output_path)
        if path.exists():
            logger.info("Skipping %s, already exists.", path)
            return str(path)

        if self.api_key == "MOCK_KEY":
            await asyncio.sleep(0.1)
            async with aiofiles.open(path, "wb") as f:
                await f.write(b"mock_audio_data")
            return str(path)

        async with aiohttp.ClientSession() as session:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-flashlite-3.1:generateText?key={self.api_key}"
            )
            headers = {"Content-Type": "application/json"}
            payload = {"text": text, "voice": self.voice}
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async with aiofiles.open(path, "wb") as f:
                    await f.write(await response.read())
                return str(path)


class ImageGeneratorFactory:
    @staticmethod
    def get_generator(provider: str, **kwargs) -> BaseImageGenerator:
        if provider.lower() == "runware":
            return RunwareImageGenerator(api_key=kwargs.get("api_key"))
        raise ValueError(f"Unknown image generator provider: {provider}")


class AudioGeneratorFactory:
    @staticmethod
    def get_generator(provider: str, **kwargs) -> BaseAudioGenerator:
        if provider.lower() == "vertex_ai":
            return VertexAITTSGenerator(api_key=kwargs.get("api_key"), voice=kwargs.get("voice"))
        raise ValueError(f"Unknown audio generator provider: {provider}")
