import json
from pathlib import Path
from typing import Any, Dict


class StateManager:
    """Manages the global state of the series, reading and writing to series_state.json."""

    def __init__(self, filepath: str = "series_state.json"):
        self.filepath = Path(filepath)
        self._initialize_state()

    def _initialize_state(self) -> None:
        """Creates an empty state file if it doesn't exist."""
        if not self.filepath.exists():
            default_state = {
                "series_id": "",
                "current_episode_target": 1,
                "style_token": "",
                "global_arc": "",
                "character_registry": {},
                "completed_episodes": [],
            }
            self.save_state(default_state)

    def load_state(self) -> Dict[str, Any]:
        """Loads and returns the current state from the JSON file."""
        with self.filepath.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self, state_data: Dict[str, Any]) -> None:
        """Writes the provided state data back to the JSON file."""
        with self.filepath.open("w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=4)

    def update_state(self, key: str, value: Any) -> None:
        """Updates a specific key in the state."""
        state = self.load_state()
        state[key] = value
        self.save_state(state)

    def get_character_description(self, character_name: str) -> str:
        """Retrieves the physical description of a character from the registry."""
        state = self.load_state()
        registry = state.get("character_registry", {})
        return registry.get(character_name)

    def mark_episode_completed(self, episode_id: str) -> None:
        """Adds an episode ID to the list of completed episodes."""
        state = self.load_state()
        completed = state.get("completed_episodes", [])
        if episode_id not in completed:
            completed.append(episode_id)
            state["completed_episodes"] = completed
            self.save_state(state)
