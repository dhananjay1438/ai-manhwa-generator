# 🎭 AI Manhwa Generator (Long-Form Edition)

An advanced, automated pipeline for generating long-form (15-20 minute) Manhwa-style narration videos for YouTube and social media. This system uses a hierarchical writing architecture to produce deeply detailed, serialized stories with consistent characters and high-quality visuals.

---

## 🚀 Key Features

- **Hierarchical Storytelling**: Breaks down stories from a high-level Bible into detailed Episode Plans, then into individual Chapters (4-6 per episode) to ensure narrative depth and bypass LLM token limits.
- **Long-Form Support**: Specifically optimized to generate 2,500-3,000 words of narration per episode, resulting in 15-20 minutes of content.
- **Consistent Manhwa Aesthetics**: Explicit prompt engineering ensures characters maintain their visual identity and the art style remains consistent (Korean Manhwa/Webtoon style).
- **Progress Tracking**: Real-time rendering progress bars via MoviePy integration so you're never in the dark during assembly.
- **Auto-Resume Logic**: Automatically saves every intermediate step (Story Bible, Episode Plans, Chapter Scripts). If a run is interrupted, it picks up exactly where it left off.
- **Clean Output Organization**: Every story run is neatly contained in `outputs/story_name_timestamp/`.

---

## 🛠️ Tech Stack

- **LLM**: Google Gemini 1.5 Flash (via Vertex AI / Google Generative AI)
- **Image Generation**: Runware (optimized for Manhwa styles)
- **Audio/TTS**: Microsoft Edge-TTS (high-quality, emotive voices)
- **Video Assembly**: MoviePy 2.x & FFmpeg
- **Dependency Management**: `uv` (Fast and reliable)

---

## 📋 Prerequisites

- **[uv](https://github.com/astral-sh/uv)**: The modern Python package manager.
- **[FFmpeg](https://ffmpeg.org/)**: Installed and available in your PATH.
    - **Note:** For subtitle support, FFmpeg must be built with `--enable-libass`.

---

## ⚙️ Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd ai-manhwa-generator
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure environment variables:**
   Copy `.env.example` to `.env` and fill in your API keys (Google Cloud, Runware, etc.).
   ```bash
   cp .env.example .env
   ```

---

## 📖 Usage

### 1. Generate a Full Series (Recommended)
The `run_live.py` script is the main orchestrator for the hierarchical long-form pipeline.

```bash
uv run python run_live.py --plot "A poor student discovered he's the heir to a trillion-dollar empire." --series "heir_reveal" --episodes 1
```

**Parameters:**
- `--plot`: The one-line hook/concept of your story.
- `--series`: A unique ID for the series (used for folder naming).
- `--episodes`: Number of episodes to generate in this run.
- `--start`: Which episode number to start from (useful for resuming).
- `--publish`: After rendering, upload the final episode video to Google Drive and YouTube.

### 2. Daily End-to-End Pipeline

Create an OAuth desktop client in Google Cloud with the Drive API and YouTube Data API enabled, then place the downloaded secret at:

```text
client-secret.json
```

Drive and YouTube authenticate separately so you can choose your personal account for Drive and your brand/channel account for YouTube. By default both flows reuse `client-secret.json`, but they write separate tokens:

```text
drive-token.json
youtube-token.json
```

The first publishing run opens one browser consent flow for Drive and one for YouTube. Later runs refresh/reuse the matching token automatically.

Run the one-time auth setup from a shell:

```bash
uv run python daily_episode.py --setup-auth
```

Test email delivery:

```bash
uv run python daily_episode.py --test-email
```

Normal daily runs are non-interactive. If either token is missing or invalid, the run fails fast and sends a Resend email notification.

Recommended `.env` values:

```bash
GOOGLE_DRIVE_CLIENT_SECRET_PATH=client-secret.json
GOOGLE_DRIVE_TOKEN_PATH=drive-token.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
GOOGLE_DRIVE_FOLDER_PATH=AI Manhwa Episodes
YOUTUBE_CLIENT_SECRET_PATH=client-secret.json
YOUTUBE_TOKEN_PATH=youtube-token.json
YOUTUBE_PRIVACY_STATUS=private
YOUTUBE_CATEGORY_ID=24
YOUTUBE_MADE_FOR_KIDS=false
RESEND_API_KEY=your_resend_api_key
NOTIFICATION_EMAIL_FROM=ai-manhwa-creator@resend.com
NOTIFICATION_EMAIL_TO=dhananjaypanage11@gmail.com
DAILY_SERIES_ID=heir_reveal
DAILY_EPISODE_PLOT="A poor student discovered he's the heir to a trillion-dollar empire."
```

Use `GOOGLE_DRIVE_FOLDER_ID` when you know the exact folder ID. If it is blank, `GOOGLE_DRIVE_FOLDER_PATH` is used and missing folders are created.

Generate, publish to Drive/YouTube, update daily state, and email success/failure:

```bash
uv run python daily_episode.py
```

`daily_episode.py` is designed for a systemd timer. It stores progress in `daily_episode_state.json`, generates exactly the next episode, and advances the state only after the run finishes.

Example service command:

```ini
ExecStart=/usr/bin/env uv run python /path/to/ai-manhwa-generator/daily_episode.py
WorkingDirectory=/path/to/ai-manhwa-generator
```

Use `--skip-publish` only for a dry generation run.

### 3. Schedule an Existing Series

Use this for videos already rendered under `outputs/<series_timestamp>/`. It generates YouTube titles, descriptions, and tags from the saved story artifacts, then uploads each episode as a private scheduled video one day apart at 9 PM IST.

```bash
uv run python schedule_existing_series.py outputs/billionaire_revenge_20260503_000128
```

Set the first scheduled date explicitly:

```bash
uv run python schedule_existing_series.py outputs/billionaire_revenge_20260503_000128 --first-date 2026-05-04
```

The script writes:

```text
episode_01_youtube_metadata.json
youtube_schedule_manifest.json
```

Rerunning the script skips episodes already present in the schedule manifest.

### 4. Running the API Server
For remote triggering of episodes:
```bash
uv run start
```

---

## 📂 Output Structure

All generated content is stored in the `outputs/` directory:
```text
outputs/
└── series_id_timestamp/
    ├── story_bible.json           # Characters, settings, and full plot beats
    ├── episode_plan.json          # High-level plan for all episodes
    ├── episode_01_chapter_plan.json # Plan for internal chapters
    ├── episode_01_chapter_01.json # Detailed script for chapter 1
    ├── ...
    ├── episode_01_script.json     # Stitched final episode script
    ├── ep_series_id_1_assets/     # Raw images, audio, and subtitles
    └── ep_series_id_1_final.mp4   # THE FINAL VIDEO
```

---

## 🎨 Design Philosophy

- **Casual over Formal**: The protagonist starts in casual/streetwear (hoodies, tees) to emphasize the "hidden billionaire" trope. Suits are reserved for the final reveal.
- **Narrator Intensity**: The narrator script is written in the style of viral "Manhwa Recap" channels—dramatic, hype-filled, and engaging.
- **Visual Contrast**: The pipeline explicitly plans settings to contrast poverty (shabby rooms, cheap diners) with extreme wealth (penthouses, luxury cars).

---

## 🛠️ Development

### Linting and Formatting
```bash
uv run ruff check .  # Check linting
uv run ruff format . # Format code
```
