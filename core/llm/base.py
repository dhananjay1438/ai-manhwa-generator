from abc import ABC, abstractmethod
from typing import Type
from core.types import SchemaT


class BaseLLM(ABC):

    @abstractmethod
    async def generate(self, system_prompt: str, query: str) -> str:
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Type[SchemaT]) -> SchemaT:
        pass
