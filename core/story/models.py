from typing import List
from pydantic import BaseModel, Field


class CharacterProfile(BaseModel):
    name: str = Field(description="Character's full name")
    role: str = Field(description="One of: protagonist, antagonist, ally, love_interest")
    appearance: str = Field(
        description="Extremely detailed visual description for AI image generation. "
        "Include: ethnicity, age, height, build, hair color/style, eye color, "
        "facial features, and DEFAULT outfit. Be specific enough to recreate consistently."
    )
    appearance_transformed: str = Field(
        description="Appearance AFTER the reveal/transformation. Same person but in "
        "luxury clothing, confident posture, etc. Must be recognizably the same person."
    )
    personality: str = Field(description="Core personality traits in 2-3 sentences")
    secret: str = Field(description="The hidden truth about this character (e.g., 'secretly a billionaire')")
    motivation: str = Field(description="What drives this character's actions")


class Setting(BaseModel):
    name: str = Field(description="Short setting name (e.g., 'Cheap Restaurant')")
    description: str = Field(
        description="Detailed visual description for AI image generation. "
        "Include: lighting, atmosphere, key visual elements, color palette."
    )
    contrast_setting: str = Field(
        default="",
        description="Optional luxury counterpart (e.g., 'Michelin Star Restaurant'). "
        "Used for before/after contrast scenes."
    )


class StoryBeat(BaseModel):
    beat_number: int
    title: str = Field(description="Short title for this beat")
    description: str = Field(description="What happens in this beat (2-3 sentences)")
    emotional_tone: str = Field(
        description="One of: humiliation, simmering_anger, suspicion, small_reveal, "
        "power_move, big_reveal, confrontation, triumph, consequence, cliffhanger"
    )
    characters_involved: List[str] = Field(description="Character names present in this beat")
    setting: str = Field(description="Setting name where this beat occurs")


class StoryBible(BaseModel):
    title: str = Field(description="Catchy, dramatic series title")
    logline: str = Field(description="One-sentence hook that makes someone want to watch")
    genre: str = Field(default="revenge_billionaire_reveal")
    total_beats: int = Field(description="Total number of story beats")
    characters: List[CharacterProfile] = Field(description="2-4 characters maximum")
    settings: List[Setting] = Field(description="4-6 distinct locations")
    plot_beats: List[StoryBeat] = Field(description="15-30 story beats from start to finish")
    themes: List[str] = Field(description="2-3 core themes")
    tone: str = Field(description="Overall tone description")


class EpisodePlan(BaseModel):
    episode_number: int
    title: str = Field(description="Episode title that teases the content")
    summary: str = Field(description="What happens in this episode (3-4 sentences)")
    characters_present: List[str] = Field(description="Which characters appear")
    settings_used: List[str] = Field(description="Which settings are used")
    emotional_arc: str = Field(
        description="The emotional journey of this episode "
        "(e.g., 'humiliation → simmering anger → small hint of power')"
    )
    opening_hook: str = Field(
        description="The first line the narrator says — must grab attention immediately"
    )
    cliffhanger_ending: str = Field(
        description="How this episode ends — must make viewer desperate for next episode"
    )
    beat_numbers: List[int] = Field(description="Which story beat numbers this episode covers")


class SeriesPlan(BaseModel):
    total_episodes: int
    episodes: List[EpisodePlan]


class ChapterPlan(BaseModel):
    chapter_number: int
    title: str = Field(description="Short chapter title")
    summary: str = Field(description="What happens in this chapter (3-5 sentences)")
    characters_present: List[str] = Field(description="Which characters appear")
    settings_used: List[str] = Field(description="Which settings are used")
    emotional_arc: str = Field(description="Emotional journey, e.g. 'tension → shock → anger'")
    opening_state: str = Field(
        description="1-2 sentences: how this chapter opens — narrative/emotional context"
    )
    closing_state: str = Field(
        description="1-2 sentences: how this chapter ends — handoff to next chapter"
    )
    key_moments: List[str] = Field(description="2-3 key dramatic moments that must happen")
    beat_numbers: List[int] = Field(description="Which story beat numbers this chapter covers")


class EpisodeChapterPlan(BaseModel):
    episode_number: int
    episode_title: str
    total_chapters: int
    chapters: List[ChapterPlan]
