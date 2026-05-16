"""
Per-tab setting registration modules.

Each module exposes a `register(prefs)` function that registers all
SettingDefinitions for one tab in the settings dialog. The aggregate
registration order in settings_registry._register_all_settings()
determines the visible tab order.
"""
