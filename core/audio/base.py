from abc import ABC, abstractmethod


class BaseAudioGenerator(ABC):

    @abstractmethod
    async def generate_audio(self, text: str, output_path: str) -> str:
        pass
