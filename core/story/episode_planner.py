"""Stage 2: Split a Story Bible into binge-worthy episodes."""

from core.llm.base import BaseLLM
from core.story.models import StoryBible, SeriesPlan
from core.story.prompts import EPISODE_PLANNER_PROMPT
from logger import logger


class EpisodePlanner:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def plan(self, bible: StoryBible, target_episodes: int = 10) -> SeriesPlan:
        """Takes a story bible and splits it into episode plans."""

        # Serialize the bible for the LLM
        bible_summary = bible.model_dump_json(indent=2)

        query = f"""Here is the complete Story Bible:

{bible_summary}

Split this story into exactly {target_episodes} episodes.

Each episode should:
- Cover 4-8 story beats (enough for 15-20 minutes of narration)
- Have a compelling opening hook
- End on a dramatic cliffhanger
- Feel complete enough to be satisfying, but leave the viewer wanting more
- Have enough material for 4-6 internal chapters

Plan all {target_episodes} episodes now."""

        logger.info("Stage 2: Planning %d episodes...", target_episodes)

        plan = await self.llm.generate_structured(
            f"{EPISODE_PLANNER_PROMPT}\n\n{query}", SeriesPlan
        )

        logger.info("Episode plan generated: %d episodes", len(plan.episodes))
        for ep in plan.episodes:
            logger.info("  Episode %d: %s", ep.episode_number, ep.title)

        return plan
