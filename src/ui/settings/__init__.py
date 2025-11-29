"""
Settings UI Package for LocalScribe.

Provides an extensible settings dialog with:
- Tabbed interface organized by category
- Auto-generated UI from SettingsRegistry
- Tooltips with info icons for each setting
- Immediate apply on save

Usage:
    from src.ui.settings import SettingsDialog
    SettingsDialog(parent=root, on_save_callback=my_callback)

Adding new settings:
    Add a SettingsRegistry.register() call in settings_registry.py.
    The UI will automatically include it - no other changes needed.
"""

from .settings_dialog import SettingsDialog
from .settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)
from .settings_widgets import (
    CheckboxSetting,
    DropdownSetting,
    SettingRow,
    SliderSetting,
    SpinboxSetting,
    TooltipIcon,
)

__all__ = [
    # Main dialog
    "SettingsDialog",
    # Registry
    "SettingsRegistry",
    "SettingDefinition",
    "SettingType",
    # Widgets
    "TooltipIcon",
    "SettingRow",
    "SliderSetting",
    "CheckboxSetting",
    "DropdownSetting",
    "SpinboxSetting",
]
