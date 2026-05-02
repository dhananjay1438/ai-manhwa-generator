"""Stage 3: Write a full episode script from a story bible + episode plan."""

from core.llm.base import BaseLLM
from core.story.models import StoryBible, EpisodePlan
from core.story.prompts import EPISODE_WRITER_PROMPT
from models import EpisodeScript
from logger import logger


class EpisodeWriter:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def write(
        self,
        bible: StoryBible,
        episode_plan: EpisodePlan,
        previous_cliffhanger: str = "",
    ) -> EpisodeScript:
        """Writes a full episode script from the bible and episode plan."""

        # Build character reference block
        char_ref = "\n".join(
            f"- **{c.name}** ({c.role}): {c.appearance}"
            for c in bible.characters
        )

        # Build setting reference block
        setting_ref = "\n".join(
            f"- **{s.name}**: {s.description}"
            for s in bible.settings
        )

        # Get the story beats for this episode
        relevant_beats = [
            b for b in bible.plot_beats if b.beat_number in episode_plan.beat_numbers
        ]
        beats_text = "\n".join(
            f"- Beat {b.beat_number} ({b.emotional_tone}): {b.description}"
            for b in relevant_beats
        )

        continuity = ""
        if previous_cliffhanger:
            continuity = f"\nPREVIOUS EPISODE ENDED WITH: \"{previous_cliffhanger}\"\nPick up naturally from this cliffhanger.\n"

        query = f"""Write Episode {episode_plan.episode_number}: "{episode_plan.title}"

## Episode Plan
Summary: {episode_plan.summary}
Emotional Arc: {episode_plan.emotional_arc}
Opening Hook: {episode_plan.opening_hook}
Cliffhanger Ending: {episode_plan.cliffhanger_ending}
{continuity}
## Story Beats to Cover
{beats_text}

## Character Reference (use EXACT descriptions for visual prompts)
{char_ref}

## Setting Reference (use EXACT descriptions for visual prompts)
{setting_ref}

## Characters in This Episode
{', '.join(episode_plan.characters_present)}

## Settings in This Episode
{', '.join(episode_plan.settings_used)}

Generate:
1. A narrator_script (350-500 words, dramatic recap style)
2. 15-25 visual_prompts with detailed scene descriptions
3. The cliffhanger_ending line
4. The hook_line (opening line)

IMPORTANT: In each visual prompt's raw_action_description, include the FULL character
appearance description from the reference above. Each panel must be a self-contained
image generation prompt."""

        logger.info(
            "Stage 3: Writing Episode %d — '%s'...",
            episode_plan.episode_number,
            episode_plan.title,
        )

        script = await self.llm.generate_structured(
            f"{EPISODE_WRITER_PROMPT}\n\n{query}", EpisodeScript
        )

        logger.info(
            "Episode %d written: %d panels, %d words of narration",
            script.episode_number,
            len(script.visual_prompts),
            len(script.narrator_script.split()),
        )

        return script
