import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any

from state_manager import StateManager
from compiler import PromptCompiler
from asset_factory import AssetFactory
from subtitle_generator import SubtitleGenerator
from assembler import FFmpegAssembler
from config import settings

app = FastAPI(title="V2 Static-Episodic Manhwa Engine")

# Dependency initialization
state_manager = StateManager()
prompt_compiler = PromptCompiler(state_manager)
asset_factory = AssetFactory(settings.runware_api_key, settings.elevenlabs_api_key)

class GenerationRequest(BaseModel):
    series_id: str
    script: Dict[str, Any] # Accepts the EpisodeScript dict

async def run_pipeline(series_id: str, script_data: Dict[str, Any]):
    try:
        episode_number = script_data.get("episode_number", 1)
        episode_id = f"{series_id}_{episode_number}"

        # Ensure base directories exist
        assets_dir = f"./assets/ep_{episode_id}"
        os.makedirs(assets_dir, exist_ok=True)

        print(f"Starting pipeline for episode {episode_id}")

        # Module 1: Compile Prompts
        compiled_prompts = prompt_compiler.compile_script(script_data)
        script_text = script_data.get("narrator_script", "")
        print(f"Compiled {len(compiled_prompts)} prompts.")

        # Module 2: Generate Assets (Async)
        print("Generating assets...")
        asset_paths = await asset_factory.generate_assets(episode_id, compiled_prompts, script_text)
        transcription_path = asset_paths["transcription_path"]

        # Module 3: Subtitle Engineering
        print("Generating ASS subtitles...")
        sub_gen = SubtitleGenerator(
            transcription_path=transcription_path,
            output_ass_path=os.path.join(assets_dir, "subtitles.ass")
        )
        sub_gen.generate()

        # Module 4: Assembly
        print("Assembling video...")
        assembler = FFmpegAssembler(episode_id=episode_id, assets_dir=assets_dir)
        final_video = assembler.assemble()

        print(f"Pipeline complete! Output: {final_video}")

        # Update state
        state_manager.mark_episode_completed(episode_id)

    except Exception as e:
        print(f"Pipeline failed: {e}")
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
        # We test compile it just to validate constraints (e.g. max 2 characters) before accepting the job
        prompt_compiler.compile_script(request.script)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Script validation failed: {str(e)}")

    # Add to background tasks
    background_tasks.add_task(run_pipeline, request.series_id, request.script)

    return {"status": "Accepted", "message": "Generation pipeline started in background."}

@app.get("/state")
async def get_state():
    return state_manager.load_state()
