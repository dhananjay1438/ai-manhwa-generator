"""Stage 3a: Break an episode plan into chapters for long-form writing."""

from core.llm.base import BaseLLM
from core.story.models import StoryBible, EpisodePlan, EpisodeChapterPlan
from core.story.prompts import CHAPTER_PLANNER_PROMPT
from logger import logger


class ChapterPlanner:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def plan(
        self,
        bible: StoryBible,
        episode_plan: EpisodePlan,
    ) -> EpisodeChapterPlan:
        """Breaks an episode plan into 4-6 chapters for sequential writing."""

        char_ref = "\n".join(
            f"- **{c.name}** ({c.role}): {c.appearance}"
            for c in bible.characters
        )

        setting_ref = "\n".join(
            f"- **{s.name}**: {s.description}"
            for s in bible.settings
        )

        relevant_beats = [
            b for b in bible.plot_beats if b.beat_number in episode_plan.beat_numbers
        ]
        beats_text = "\n".join(
            f"- Beat {b.beat_number} ({b.emotional_tone}): {b.description}"
            for b in relevant_beats
        )

        query = f"""Break Episode {episode_plan.episode_number}: "{episode_plan.title}" into chapters.

## Episode Plan
Summary: {episode_plan.summary}
Emotional Arc: {episode_plan.emotional_arc}
Opening Hook: {episode_plan.opening_hook}
Cliffhanger Ending: {episode_plan.cliffhanger_ending}

## Story Beats to Cover
{beats_text}

## Character Reference
{char_ref}

## Setting Reference
{setting_ref}

## Characters in This Episode
{', '.join(episode_plan.characters_present)}

## Settings in This Episode
{', '.join(episode_plan.settings_used)}

Break this episode into 4-6 chapters. Each chapter = ~3-4 minutes of narration.
Distribute the story beats across chapters logically.
Chapter 1 opens with the hook. The final chapter ends with the cliffhanger."""

        logger.info(
            "Planning chapters for Episode %d — '%s'...",
            episode_plan.episode_number,
            episode_plan.title,
        )

        plan = await self.llm.generate_structured(
            f"{CHAPTER_PLANNER_PROMPT}\n\n{query}", EpisodeChapterPlan
        )

        logger.info(
            "Episode %d chapter plan: %d chapters",
            episode_plan.episode_number,
            len(plan.chapters),
        )

        return plan
