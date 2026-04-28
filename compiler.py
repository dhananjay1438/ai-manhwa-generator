import re
from typing import List, Dict, Any
from models import EpisodeScript, VisualPrompt
from state_manager import StateManager

class PromptCompiler:
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    def compile_script(self, script_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses the EpisodeScript, injects character descriptions and style tokens,
        and validates constraints. Returns a list of compiled prompts ready for generation.
        """
        # Step 1: Parse and validate via Pydantic
        # This will automatically throw an error if characters_in_frame > 2
        script = EpisodeScript(**script_data)

        state = self.state_manager.load_state()
        style_token = state.get("style_token", "")

        compiled_prompts = []

        for panel in script.visual_prompts:
            action_desc = panel.raw_action_description

            # Step 2: Character Injection
            for char_name in panel.characters_in_frame:
                char_desc = self.state_manager.get_character_description(char_name)
                if char_desc:
                    # Replace whole word matches of the character name with their description
                    # using regex to ensure we don't partially replace words
                    pattern = re.compile(rf'\b{re.escape(char_name)}\b', re.IGNORECASE)
                    action_desc = pattern.sub(f"{char_name} ({char_desc})", action_desc)

            # Step 3: Style Injection
            final_prompt = f"{style_token} {action_desc}".strip()

            compiled_prompts.append({
                "panel_id": panel.panel_id,
                "prompt": final_prompt
            })

        return compiled_prompts
