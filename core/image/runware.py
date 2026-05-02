import uuid
import asyncio
from pathlib import Path

import aiofiles
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from core.image.base import BaseImageGenerator
from logger import logger


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
                    "taskUUID": str(uuid.uuid4()),
                    "positivePrompt": prompt,
                    "model": "runware:100@1",
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
