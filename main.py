from pathlib import Path
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from assembler import FFmpegAssembler
from asset_factory import AssetFactory
from compiler import PromptCompiler
from config import settings
from logger import logger
from state_manager import StateManager
from subtitle_generator import SubtitleGenerator

app = FastAPI(title="V2 Static-Episodic Manhwa Engine")

# Dependency initialization
state_manager = StateManager()
prompt_compiler = PromptCompiler(state_manager)
asset_factory = AssetFactory(
    runware_api_key=settings.runware_api_key,
    google_api_key=settings.google_api_key,
    google_tts_voice=settings.google_tts_voice,
    enable_whisper=settings.enable_whisper,
)


class GenerationRequest(BaseModel):
    series_id: str
    script: Dict[str, Any]  # Accepts the EpisodeScript dict


async def run_pipeline(series_id: str, script_data: Dict[str, Any]):
    try:
        episode_number = script_data.get("episode_number", 1)
        episode_id = f"{series_id}_{episode_number}"

        # Ensure base directories exist
        assets_dir = Path("./assets") / f"ep_{episode_id}"
        assets_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting pipeline for episode %s", episode_id)

        # Module 1: Compile Prompts
        compiled_prompts = prompt_compiler.compile_script(script_data)
        script_text = script_data.get("narrator_script", "")
        logger.info("Compiled %d prompts.", len(compiled_prompts))

        # Module 2: Generate Assets (Async)
        logger.info("Generating assets...")
        asset_paths = await asset_factory.generate_assets(episode_id, compiled_prompts, script_text)
        transcription_path = asset_paths["transcription_path"]

        # Module 3: Subtitle Engineering
        if settings.enable_whisper and transcription_path:
            logger.info("Generating ASS subtitles...")
            sub_gen = SubtitleGenerator(
                transcription_path=transcription_path,
                output_ass_path=str(assets_dir / "subtitles.ass"),
            )
            sub_gen.generate()
        else:
            logger.info("Skipping subtitles (Whisper disabled)...")

        # Module 4: Assembly
        logger.info("Assembling video...")
        assembler = FFmpegAssembler(
            episode_id=episode_id,
            assets_dir=str(assets_dir),
            enable_subtitles=settings.enable_whisper,
        )
        final_video = assembler.assemble()

        logger.info("Pipeline complete! Output: %s", final_video)

        # Update state
        state_manager.mark_episode_completed(episode_id)

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        # In a real system, you'd log this properly and potentially alert.
        raise


@app.post("/generate")
async def start_generation(request: GenerationRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to trigger the episode generation pipeline.
    Runs asynchronously in the background.
    """
    # Quick synchronous validation via Pydantic model inside PromptCompiler
    try:
        # We test compile it just to validate constraints (e.g. max 2 characters)
        prompt_compiler.compile_script(request.script)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Script validation failed: {str(e)}") from e

    # Add to background tasks
    background_tasks.add_task(run_pipeline, request.series_id, request.script)

    return {"status": "Accepted", "message": "Generation pipeline started in background."}


@app.get("/state")
async def get_state():
    return state_manager.load_state()
