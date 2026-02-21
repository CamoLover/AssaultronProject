"""
Settings Manager - Persistent storage for user settings

Copyright (c) 2026 Evan Escabasse.
Licensed under the MIT License - see LICENSE file for details.

This module handles loading and saving user settings to a JSON file,
including LLM model selections, language preferences, and other configurations.
"""

import json
import os
from typing import Dict, Any, Optional


class SettingsManager:
    """Manages persistent user settings stored in JSON file"""

    def __init__(self, settings_file: str = "ai-data/settings.json"):
        """
        Initialize settings manager.

        Args:
            settings_file: Path to the settings JSON file
        """
        self.settings_file = settings_file
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[SETTINGS] Failed to load settings: {e}")

        # Return default settings if file doesn't exist or loading failed
        return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings structure"""
        return {
            "llm": {
                "ollama_model": "gemma3:4b",
                "gemini_model": "gemini-2.0-flash-exp",
                "openrouter_model": "deepseek/deepseek-v3.2"
            },
            "language": "en",
            "verbosity": 2,
            "voice_model": "f4_robot_assaultron"
        }

    def _save_settings(self) -> bool:
        """Save settings to JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)

            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"[SETTINGS ERROR] Failed to save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value by key (supports nested keys with dot notation).

        Args:
            key: Setting key (e.g., "llm.ollama_model")
            default: Default value if key doesn't exist

        Returns:
            Setting value or default
        """
        keys = key.split('.')
        value = self.settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value by key (supports nested keys with dot notation).

        Args:
            key: Setting key (e.g., "llm.ollama_model")
            value: Value to set

        Returns:
            True if successful, False otherwise
        """
        keys = key.split('.')

        # Navigate to the parent dict
        current = self.settings
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the value
        current[keys[-1]] = value

        return self._save_settings()

    def get_llm_model(self, provider: str) -> Optional[str]:
        """
        Get the configured model for a specific LLM provider.

        Args:
            provider: Provider name ("ollama", "gemini", or "openrouter")

        Returns:
            Model name or None
        """
        return self.get(f"llm.{provider}_model")

    def set_llm_model(self, provider: str, model: str) -> bool:
        """
        Set the model for a specific LLM provider.

        Args:
            provider: Provider name ("ollama", "gemini", or "openrouter")
            model: Model name

        Returns:
            True if successful, False otherwise
        """
        return self.set(f"llm.{provider}_model", model)

    def get_all_llm_models(self) -> Dict[str, str]:
        """Get all configured LLM models"""
        return {
            "ollama": self.get_llm_model("ollama"),
            "gemini": self.get_llm_model("gemini"),
            "openrouter": self.get_llm_model("openrouter")
        }
