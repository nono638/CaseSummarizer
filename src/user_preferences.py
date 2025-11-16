"""
User Preferences Manager for LocalScribe
Manages user-specific preferences like default prompts per model.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


class UserPreferencesManager:
    """
    Manages user preferences stored in config/user_preferences.json.

    Handles default prompt selection per model with graceful fallbacks.
    """

    def __init__(self, preferences_file: Path):
        """
        Initialize the preferences manager.

        Args:
            preferences_file: Path to user_preferences.json
        """
        self.preferences_file = Path(preferences_file)
        self._preferences = self._load_preferences()

    def _load_preferences(self) -> Dict[str, Any]:
        """
        Load preferences from JSON file.

        Returns:
            dict: User preferences, or default structure if file not found
        """
        default_structure = {
            "model_defaults": {},
            "last_used_model": None
        }

        try:
            if self.preferences_file.exists():
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                    # Ensure structure exists
                    if "model_defaults" not in prefs:
                        prefs["model_defaults"] = {}
                    return prefs
            else:
                return default_structure

        except (json.JSONDecodeError, Exception):
            # If file is corrupted, return defaults
            return default_structure

    def _save_preferences(self) -> None:
        """Save preferences to JSON file."""
        try:
            # Ensure directory exists
            self.preferences_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(self._preferences, f, indent=2)

        except Exception as e:
            # Log error but don't crash
            print(f"Warning: Could not save user preferences: {e}")

    def get_default_prompt(self, model_name: str) -> Optional[str]:
        """
        Get the user's preferred default prompt for a model.

        Args:
            model_name: Name of the model (e.g., 'phi-3-mini')

        Returns:
            Preset ID string, or None if no default set
        """
        return self._preferences.get("model_defaults", {}).get(model_name)

    def set_default_prompt(self, model_name: str, preset_id: str) -> None:
        """
        Set the default prompt for a model.

        Args:
            model_name: Name of the model (e.g., 'phi-3-mini')
            preset_id: Preset identifier (e.g., 'factual-summary')
        """
        if "model_defaults" not in self._preferences:
            self._preferences["model_defaults"] = {}

        self._preferences["model_defaults"][model_name] = preset_id
        self._save_preferences()

    def get_last_used_model(self) -> Optional[str]:
        """Get the last model the user loaded."""
        return self._preferences.get("last_used_model")

    def set_last_used_model(self, model_name: str) -> None:
        """
        Set the last used model.

        Args:
            model_name: Name of the model
        """
        self._preferences["last_used_model"] = model_name
        self._save_preferences()

    def clear_default_prompt(self, model_name: str) -> None:
        """
        Clear the default prompt for a model.

        Args:
            model_name: Name of the model
        """
        if "model_defaults" in self._preferences:
            self._preferences["model_defaults"].pop(model_name, None)
            self._save_preferences()


# Global instance
_user_prefs = None


def get_user_preferences(preferences_file: Path = None) -> UserPreferencesManager:
    """
    Get the global UserPreferencesManager instance (singleton pattern).

    Args:
        preferences_file: Optional path to preferences file (only used on first call)

    Returns:
        UserPreferencesManager: The global preferences instance
    """
    global _user_prefs

    if _user_prefs is None:
        if preferences_file is None:
            from .config import CONFIG_DIR
            preferences_file = CONFIG_DIR / "user_preferences.json"

        _user_prefs = UserPreferencesManager(preferences_file)

    return _user_prefs
