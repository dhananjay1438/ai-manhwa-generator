"""Stage 3b: Write a single chapter of an episode."""

import asyncio

from core.llm.base import BaseLLM
from core.story.models import StoryBible, ChapterPlan
from core.story.prompts import CHAPTER_WRITER_PROMPT
from models import ChapterScript
from logger import logger


class ChapterWriter:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def write(
        self,
        bible: StoryBible,
        chapter_plan: ChapterPlan,
        episode_number: int,
        episode_title: str,
        total_chapters: int,
        previous_closing: str = "",
    ) -> ChapterScript:
        """Writes a single chapter of an episode."""

        # Only include characters relevant to this chapter
        char_ref = "\n".join(
            f"- **{c.name}** ({c.role}): {c.appearance}"
            for c in bible.characters
            if c.name in chapter_plan.characters_present
        )

        setting_ref = "\n".join(
            f"- **{s.name}**: {s.description}"
            for s in bible.settings
            if s.name in chapter_plan.settings_used
        )

        relevant_beats = [
            b for b in bible.plot_beats if b.beat_number in chapter_plan.beat_numbers
        ]
        beats_text = "\n".join(
            f"- Beat {b.beat_number} ({b.emotional_tone}): {b.description}"
            for b in relevant_beats
        )

        continuity = ""
        if previous_closing:
            continuity = f'\nPREVIOUS CHAPTER ENDED WITH: "{previous_closing}"\nContinue naturally from this point.\n'

        is_first = chapter_plan.chapter_number == 1
        is_last = chapter_plan.chapter_number == total_chapters

        position_note = ""
        if is_first:
            position_note = "\nThis is the FIRST chapter — open with the episode's hook. Grab the viewer immediately.\n"
        if is_last:
            position_note = "\nThis is the FINAL chapter — end with a dramatic cliffhanger that makes viewers desperate for the next episode.\n"

        query = f"""Write Chapter {chapter_plan.chapter_number} of {total_chapters} for Episode {episode_number}: "{episode_title}"

## Chapter Plan
Title: {chapter_plan.title}
Summary: {chapter_plan.summary}
Emotional Arc: {chapter_plan.emotional_arc}
Opening State: {chapter_plan.opening_state}
Closing State: {chapter_plan.closing_state}
Key Moments: {', '.join(chapter_plan.key_moments)}
{continuity}{position_note}
## Story Beats to Cover
{beats_text}

## Character Reference (use EXACT descriptions for visual prompts)
{char_ref}

## Setting Reference (use EXACT descriptions for visual prompts)
{setting_ref}

Generate:
1. narration: 400-600 words of dramatic narrator script for this chapter
2. visual_prompts: 12-16 panels with detailed manhwa-style scene descriptions
3. closing_line: the last narrative line of this chapter

IMPORTANT: In each visual prompt's raw_action_description, you MUST include:
- The manhwa art style prefix: "Korean manhwa webtoon art style, cel-shaded, bold outlines, dramatic lighting, expressive anime eyes, vibrant colors."
- The FULL character appearance description from the reference above
- Camera angle and emotional expression
- Each panel must be a self-contained image generation prompt"""

        logger.info(
            "   ✍️  Writing Chapter %d/%d of Episode %d...",
            chapter_plan.chapter_number,
            total_chapters,
            episode_number,
        )

        script = await self.llm.generate_structured(
            f"{CHAPTER_WRITER_PROMPT}\n\n{query}", ChapterScript
        )

        logger.info(
            "   ✅ Chapter %d: %d panels, %d words",
            script.chapter_number,
            len(script.visual_prompts),
            len(script.narration.split()),
        )

        # Small delay between chapter writes to respect rate limits
        await asyncio.sleep(2)

        return script
