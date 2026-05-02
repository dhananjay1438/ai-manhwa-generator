from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class VisualPrompt(BaseModel):
    panel_id: int
    characters_in_frame: List[str] = Field(..., max_length=2)  # Maximum of 2.
    raw_action_description: str = Field(
        description="Complete visual description for AI image generation. "
        "Must include character appearances, setting, camera angle, and emotional expression."
    )
    camera_angle: str = Field(
        default="medium_shot",
        description="One of: close_up, medium_shot, wide_shot, low_angle, high_angle"
    )

    @model_validator(mode="after")
    def check_character_limit(self):
        if len(self.characters_in_frame) > 2:
            raise ValueError("Maximum of 2 characters allowed in frame.")
        return self


class EpisodeScript(BaseModel):
    episode_number: int
    title: str = Field(default="", description="Episode title")
    hook_line: str = Field(default="", description="Opening hook to grab viewers")
    narrator_script: str  # 2500-3000 words for 15-20 min episodes
    visual_prompts: List[VisualPrompt]  # 60-80 panels across chapters
    cliffhanger_ending: str  # Explicit directive: mid-scene on critical revelation


class ChapterScript(BaseModel):
    chapter_number: int
    title: str = Field(default="", description="Chapter title")
    narration: str = Field(description="Narration text for this chapter, 400-600 words")
    visual_prompts: List[VisualPrompt]  # 12-16 panels
    closing_line: str = Field(description="The last narrative line of this chapter")
