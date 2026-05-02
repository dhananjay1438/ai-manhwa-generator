import os
from core.llm.base import BaseLLM
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from typing import Type
from core.types import SchemaT


class Gemini(BaseLLM):
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        temperature: float = 1.0,
    ) -> None:

        if not settings.GOOGLE_APPLICATION_CREDENTIALS:
            raise EnvironmentError("GOOGLE_APPLICATION_CREDENTIALS not set")

        if not settings.GOOGLE_CLOUD_LOCATION:
            raise EnvironmentError("GOOGLE_CLOUD_LOCATION not set")

        if not settings.GOOGLE_CLOUD_PROJECT:
            raise EnvironmentError("GOOGLE_CLOUD_PROJECT not set")

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

        self.client = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            location=settings.GOOGLE_CLOUD_LOCATION,
            project=settings.GOOGLE_CLOUD_PROJECT,
        )

    async def generate(self, system_prompt: str, query: str) -> str:

        messages = [
            ("ai", system_prompt),
            ("human", query),
        ]
        response = await self.client.ainvoke(messages)

        return response.text

    async def generate_structured(self, prompt: str, schema: Type[SchemaT]) -> SchemaT:

        structured_llm = self.client.with_structured_output(schema)
        response = await structured_llm.ainvoke(prompt)

        try:
            if isinstance(response, schema):
                return response

            # If response is a dict, validate it against the schema
            if isinstance(response, dict):
                return schema.model_validate(response)

            raise ValueError(f"Unexpected response type: {type(response)}")
        except Exception as e:
            raise RuntimeError("Gemini failed to generate structured output") from e
