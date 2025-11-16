"""
Prompt Template Manager for LocalScribe
Manages model-specific prompt templates with validation and preset discovery.
"""

from pathlib import Path
from typing import List, Dict, Optional
import re

# Generic fallback prompt template (based on factual-summary)
# Used when no prompts exist for a model
GENERIC_FALLBACK_TEMPLATE = """<|system|>
You are a legal document summarizer. Your role is to provide clear, objective, factual summaries of legal documents without interpretation or speculation.
<|end|>
<|user|>
Summarize the following legal document with these requirements:

WORD COUNT: Between {min_words} and {max_words_range} words (target: {max_words} words)

FOCUS ON FACTS:
- Identify all parties involved (plaintiffs, defendants, attorneys, judges)
- State the claims, charges, or legal issues presented
- Report procedural status and timeline of events
- List key facts and evidence mentioned
- Note any rulings, decisions, or outcomes

OUTPUT STYLE:
- Write in clear, plain language
- Present facts objectively without analysis
- Use active voice and affirmative statements
- Structure information chronologically when possible
- Do NOT speculate, interpret motives, or analyze strategy
- Do NOT include labels, headers, or meta-commentary in your response

DOCUMENT:
---
{case_text}
---
<|end|>
<|assistant|>
"""


class PromptTemplateManager:
    """
    Manages prompt templates for different AI models.

    Templates are organized by model in config/prompts/{model_name}/
    Each template file can use variables: {min_words}, {max_words},
    {max_words_range}, {case_text}
    """

    def __init__(self, prompts_base_dir: Path):
        """
        Initialize the template manager.

        Args:
            prompts_base_dir: Base directory containing model-specific prompt folders
        """
        self.prompts_base_dir = Path(prompts_base_dir)
        self._cache = {}  # Template cache to avoid repeated file reads

    def get_available_models(self) -> List[str]:
        """
        Get list of models that have prompt templates.

        Returns:
            List of model names (directory names in prompts_base_dir)
        """
        if not self.prompts_base_dir.exists():
            return []

        return [
            d.name for d in self.prompts_base_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]

    def get_available_presets(self, model_name: str) -> List[Dict[str, str]]:
        """
        Get available prompt presets for a specific model.

        Args:
            model_name: Name of the model (e.g., 'phi-3-mini')

        Returns:
            List of dicts with 'name' and 'file_path' keys
        """
        model_dir = self.prompts_base_dir / model_name
        if not model_dir.exists():
            return []

        presets = []
        for template_file in model_dir.glob('*.txt'):
            # Convert filename to display name (e.g., "factual-summary" -> "Factual Summary")
            display_name = template_file.stem.replace('-', ' ').replace('_', ' ').title()
            presets.append({
                'name': display_name,
                'id': template_file.stem,
                'file_path': str(template_file)
            })

        return sorted(presets, key=lambda x: x['name'])

    def load_template(
        self,
        model_name: str,
        preset_id: str,
        use_cache: bool = True
    ) -> str:
        """
        Load a prompt template from file.

        Args:
            model_name: Name of the model (e.g., 'phi-3-mini')
            preset_id: Template identifier (filename without extension)
            use_cache: Whether to use cached template if available

        Returns:
            Template content as string

        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template is invalid
        """
        cache_key = f"{model_name}/{preset_id}"

        # Check cache first
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # Load from file
        template_path = self.prompts_base_dir / model_name / f"{preset_id}.txt"

        if not template_path.exists():
            raise FileNotFoundError(
                f"Template not found: {template_path}\n"
                f"Available models: {self.get_available_models()}"
            )

        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        # Validate template
        self.validate_template(template, template_path)

        # Cache and return
        self._cache[cache_key] = template
        return template

    def validate_template(self, template: str, template_path: Path = None) -> None:
        """
        Validate that a template has required elements.

        Args:
            template: Template content to validate
            template_path: Optional path for better error messages

        Raises:
            ValueError: If template is missing required elements
        """
        errors = []

        # Check for required Phi-3 chat tokens
        required_tokens = ['<|system|>', '<|user|>', '<|end|>', '<|assistant|>']
        for token in required_tokens:
            if token not in template:
                errors.append(f"Missing required token: {token}")

        # Check for required template variables
        required_vars = ['{min_words}', '{max_words}', '{max_words_range}', '{case_text}']
        for var in required_vars:
            if var not in template:
                errors.append(f"Missing required variable: {var}")

        # Check template structure
        if template.find('<|system|>') > template.find('<|user|>'):
            errors.append("<|system|> must come before <|user|>")

        if template.find('<|user|>') > template.find('<|assistant|>'):
            errors.append("<|user|> must come before <|assistant|>")

        # Raise error if validation failed
        if errors:
            location = f" in {template_path}" if template_path else ""
            raise ValueError(
                f"Template validation failed{location}:\n" +
                "\n".join(f"  - {error}" for error in errors)
            )

    def format_template(
        self,
        template: str,
        min_words: int,
        max_words: int,
        max_words_range: int,
        case_text: str
    ) -> str:
        """
        Format a template with provided values.

        Args:
            template: Template string with {variables}
            min_words: Minimum word count
            max_words: Target word count
            max_words_range: Maximum word count
            case_text: Legal document text to summarize

        Returns:
            Formatted prompt ready for model input
        """
        return template.format(
            min_words=min_words,
            max_words=max_words,
            max_words_range=max_words_range,
            case_text=case_text
        )

    def get_default_preset_id(self, model_name: str) -> Optional[str]:
        """
        Get the default preset for a model (first alphabetically).

        Args:
            model_name: Name of the model

        Returns:
            Preset ID string, or None if no presets available
        """
        presets = self.get_available_presets(model_name)
        if not presets:
            return None
        return presets[0]['id']

    def clear_cache(self):
        """Clear the template cache."""
        self._cache.clear()

    def ensure_generic_fallback(self, model_name: str) -> None:
        """
        Ensure a generic fallback prompt exists for a model.

        If the model directory has no prompts, creates a 'generic-summary.txt'
        file with the standard fallback template.

        Args:
            model_name: Name of the model (e.g., 'phi-3-mini')
        """
        model_dir = self.prompts_base_dir / model_name

        # Check if any prompts exist
        presets = self.get_available_presets(model_name)

        if not presets:
            # No prompts found - create generic fallback
            model_dir.mkdir(parents=True, exist_ok=True)
            generic_file = model_dir / "generic-summary.txt"

            if not generic_file.exists():
                with open(generic_file, 'w', encoding='utf-8') as f:
                    f.write(GENERIC_FALLBACK_TEMPLATE)

                print(f"Created generic fallback prompt for {model_name}")

    def get_best_default_preset(
        self,
        model_name: str,
        user_preference: Optional[str] = None
    ) -> str:
        """
        Get the best default preset to use for a model.

        Priority order:
        1. User's saved preference (if exists and file found)
        2. First preset alphabetically
        3. 'generic-summary' if no other presets exist

        Args:
            model_name: Name of the model
            user_preference: User's preferred preset ID (from preferences)

        Returns:
            Preset ID to use as default
        """
        # Ensure generic fallback exists
        self.ensure_generic_fallback(model_name)

        # Get available presets
        presets = self.get_available_presets(model_name)

        if not presets:
            return "generic-summary"  # Shouldn't happen after ensure_generic_fallback

        # Try user preference first
        if user_preference:
            preset_ids = [p['id'] for p in presets]
            if user_preference in preset_ids:
                return user_preference

        # Fall back to first preset alphabetically
        return presets[0]['id']
