"""Stage 1: Generate a complete Story Bible from a one-line plot."""

from core.llm.base import BaseLLM
from core.story.models import StoryBible
from core.story.prompts import STORY_BIBLE_PROMPT
from logger import logger


class BibleGenerator:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate(self, plot: str) -> StoryBible:
        """Takes a one-line plot and generates a full story bible."""

        query = f"""Create a complete Story Bible for the following plot:

PLOT: {plot}

Generate:
1. A catchy, dramatic title
2. A one-sentence logline/hook
3. 2-4 characters with EXTREMELY detailed visual descriptions (manhwa/anime style)
   - The "secretly rich" protagonist should dress CASUALLY — hoodies, t-shirts, streetwear. NOT suits.
   - Only dress them up AFTER the big reveal.
4. 4-6 distinct settings with visual descriptions
5. 20-40 story beats from start to finish (we need enough for long-form 15-20 min episodes)
6. Core themes and tone

Remember: This is a revenge/billionaire reveal story. Make it ADDICTIVE."""

        logger.info("Stage 1: Generating Story Bible from plot...")

        bible = await self.llm.generate_structured(
            f"{STORY_BIBLE_PROMPT}\n\n{query}", StoryBible
        )

        logger.info(
            "Story Bible generated: '%s' — %d characters, %d settings, %d beats",
            bible.title,
            len(bible.characters),
            len(bible.settings),
            len(bible.plot_beats),
        )

        return bible
