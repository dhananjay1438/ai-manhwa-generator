from typing import Dict
from pydantic import BaseModel, Field

from core.llm.base import BaseLLM
from logger import logger
from models import EpisodeScript
from state_manager import StateManager


class StoryGenerationResult(BaseModel):
    new_characters: Dict[str, str] = Field(
        description="New characters introduced in this episode mapped to their visual descriptions. Example: {'Hero': 'Tall man, black hair, glowing blue eyes'}"
    )
    script: EpisodeScript


SYSTEM_PROMPT = """You are an expert Manhwa/Anime writer. You write gripping, action-packed scripts.
You take a plot summary and expand it into a full episode.

RULES:
1. narrator_script should be a dramatic, hype-filled recap/narration of the episode's events (350-450 words).
2. visual_prompts should break the events down into distinct panels (5-10 panels).
3. Characters in frames must be tracked. If you introduce a new character, add them to `new_characters` with a detailed physical description for image generation.
4. MAXIMUM 2 characters per visual prompt panel.
5. cliffhanger_ending must be a dramatic final thought that leaves the viewer wanting more.
6. raw_action_description in visual_prompts should be vivid, cinematic scene descriptions suitable for AI image generation."""


class StoryGenerator:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_episode(
        self, plot_summary: str, episode_number: int, current_state: StateManager
    ) -> StoryGenerationResult:
        """
        Takes a plot summary and current state, and generates a full episode script + characters.
        """
        existing_chars = current_state.load_state().get("character_registry", {})

        query = f"""
Episode Number: {episode_number}
Plot Summary: {plot_summary}

Currently known characters and their descriptions: {existing_chars}

Generate the episode script and any new characters needed!
"""

        logger.info("Calling LLM to generate script from plot...")

        result = await self.llm.generate_structured(
            f"{SYSTEM_PROMPT}\n\n{query}", StoryGenerationResult
        )

        return result
