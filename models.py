from typing import List

from pydantic import BaseModel, Field, model_validator


class VisualPrompt(BaseModel):
    panel_id: int
    characters_in_frame: List[str] = Field(..., max_length=2)  # Maximum of 2.
    raw_action_description: str

    @model_validator(mode="after")
    def check_character_limit(self):
        if len(self.characters_in_frame) > 2:
            raise ValueError("Maximum of 2 characters allowed in frame.")
        return self


class EpisodeScript(BaseModel):
    episode_number: int
    narrator_script: str  # 350-450 words (approx. 2-3 minutes of audio).
    visual_prompts: List[VisualPrompt]  # 25 to 35 panels
    cliffhanger_ending: str  # Explicit directive: mid-scene on critical revelation
