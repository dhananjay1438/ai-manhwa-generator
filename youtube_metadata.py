from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from core.llm.base import BaseLLM
from logger import logger

_TAGS_TOTAL_LIMIT = 480
_TAG_INDIVIDUAL_LIMIT = 30
_TITLE_LIMIT = 100
_TIMESTAMP_RE = re.compile(r"[,\s]*(?<!\d)(\d{1,2}:\d{2})\s*[-–—]\s*")
_KNOWN_HEADERS = (
    "Episode Summary:",
    "Chapters:",
    "Keywords:",
    "Hashtags:",
    "About This Series:",
)
_PART_SUFFIX_RE = re.compile(r"\s*[\-|:|]\s*Part\s+\d+\s*$", re.IGNORECASE)


class YouTubeMetadata(BaseModel):
    video_title: str = Field(description="Clickable YouTube video title")
    video_description: str = Field(description="Formatted YouTube description")
    tags: list[str] = Field(description="YouTube tags without hashtag prefixes")


class EpisodeMetadataContext(BaseModel):
    series_title: str
    series_logline: str
    episode_number: int
    episode_title: str
    episode_summary: str
    hook_line: str
    cliffhanger_ending: str
    chapters: list[str]
    series_title_template: str | None = None


METADATA_PROMPT = """
# ROLE
You are a senior YouTube growth strategist for viral manhwa recap channels.
You understand revenge arcs, billionaire reveals, hidden heir stories, betrayal hooks,
and serialized cliffhanger packaging.

# TASK
Generate YouTube metadata for this manhwa recap episode.

SERIES TITLE: {series_title}
SERIES LOGLINE: {series_logline}
EPISODE NUMBER: {episode_number}
EPISODE TITLE: {episode_title}
EPISODE SUMMARY: {episode_summary}
OPENING HOOK: {hook_line}
CLIFFHANGER: {cliffhanger_ending}

CHAPTERS:
{chapters_block}

# TITLE RULES
- Hard cap: 100 characters. Aim for 70-95.
- This is a serialized channel. The final uploaded title should feel connected across
  episodes by using a stable series title plus the part number.
- Must be dramatic and clickable, but not spammy.
- Include the strongest hook from the episode: betrayal, poor husband, secret heir,
  billionaire reveal, black card, ex-wife regret, revenge, chairman, or similar.
- Include "Manhwa Recap" near the end when it fits naturally.
- No emojis. No ALL CAPS. No excessive punctuation.
- Do not invent plot facts that are not in the episode context.

# DESCRIPTION RULES
Write in this structure with real line breaks:

[HOOK - 2 short sentences]
Open with the strongest betrayal/reveal hook and make the viewer curious.

Episode Summary:
3-5 sentences summarizing the episode without spoiling the entire series.

Chapters:
00:00 - <Chapter Title>
00:00 - <Chapter Title>
(Use 00:00 placeholders for every chapter.)

About This Series:
2-3 sentences explaining this is a serialized manhwa/webtoon-style recap with revenge,
drama, hidden identity, billionaire reveal, and cliffhanger storytelling.

Keywords:
8-10 comma-separated phrases, not hashtags.

Hashtags:
Exactly 5 hashtags on one line. Always include #manhwa #manhwarecap #webtoon.

# TAGS RULES
Return 12-15 lowercase tags, no '#' prefix. Put episode-specific tags first.
Include a mix of: manhwa recap, webtoon recap, revenge manhwa, billionaire manhwa,
hidden heir, ex wife regret, poor husband, secret identity, korean manhwa, drama recap.

# OUTPUT
Return strictly the JSON object matching the YouTubeMetadata schema.
"""


def _normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in tags:
        tag = raw.strip().lstrip("#").lower()
        if not tag:
            continue
        if len(tag) > _TAG_INDIVIDUAL_LIMIT:
            tag = tag[:_TAG_INDIVIDUAL_LIMIT].rstrip()
        if tag in seen:
            continue
        seen.add(tag)
        cleaned.append(tag)

    def total_len(items: list[str]) -> int:
        return sum(len(item) for item in items) + max(0, len(items) - 1)

    while cleaned and total_len(cleaned) > _TAGS_TOTAL_LIMIT:
        cleaned.pop()
    return cleaned


def _normalize_description(description: str) -> str:
    if not description:
        return description

    text = description.replace("\\n", "\n").replace("\r\n", "\n")
    text = _TIMESTAMP_RE.sub(lambda match: "\n" + match.group(1) + " - ", text)
    for header in _KNOWN_HEADERS:
        text = re.sub(r"\s*" + re.escape(header) + r"\s*", "\n\n" + header + "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class MetadataGenerator:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_metadata(self, context: EpisodeMetadataContext) -> YouTubeMetadata:
        chapters_block = "\n".join(f"- {chapter}" for chapter in context.chapters)
        prompt = METADATA_PROMPT.format(
            series_title=context.series_title,
            series_logline=context.series_logline,
            episode_number=context.episode_number,
            episode_title=context.episode_title,
            episode_summary=context.episode_summary,
            hook_line=context.hook_line,
            cliffhanger_ending=context.cliffhanger_ending,
            chapters_block=chapters_block,
        )

        logger.info("Generating YouTube metadata for episode %d...", context.episode_number)
        metadata = await self.llm.generate_structured(prompt, YouTubeMetadata)
        if len(metadata.video_title) > _TITLE_LIMIT:
            metadata.video_title = metadata.video_title[:_TITLE_LIMIT].rstrip()
        metadata.video_description = _normalize_description(metadata.video_description)
        metadata.tags = _normalize_tags(metadata.tags)
        return metadata


def normalize_series_title_template(raw_title: str) -> str:
    title = _PART_SUFFIX_RE.sub("", raw_title).strip()
    if len(title) > 86:
        title = title[:86].rstrip(" .:-")
    return title


def serial_video_title(series_title_template: str, episode_number: int) -> str:
    base = normalize_series_title_template(series_title_template)
    title = f"{base} - Part {episode_number}"
    if len(title) <= _TITLE_LIMIT:
        return title

    suffix = f" - Part {episode_number}"
    return f"{base[: _TITLE_LIMIT - len(suffix)].rstrip(' .:-')}{suffix}"


def save_metadata(path: Path, metadata: YouTubeMetadata) -> None:
    path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
