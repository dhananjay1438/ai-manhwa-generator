from abc import ABC, abstractmethod


class BaseImageGenerator(ABC):

    @abstractmethod
    async def generate_image(self, prompt: str, output_path: str) -> str:
        pass
