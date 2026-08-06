"""
Core configuration management for JARVIS.
=========================================
Handles all application settings via environment variables and config files.
Uses pydantic-settings for validated configuration with type coercion.

Settings are loaded in priority order:
    1. Environment variables (highest priority)
    2. .env file
    3. Default values (lowest priority)

Example:
    from jarvis.config import get_settings
    settings = get_settings()
    print(settings.openai_api_key)
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent


class AISettings(BaseSettings):
    """AI/LLM provider configuration."""
    model_config = {"env_prefix": "AI_"}

    provider: str = Field(default="gemini", description="AI provider: gemini, openai, local, anthropic")
    model: str = Field(default="gemini-2.0-flash", description="Model identifier")
    api_key: Optional[str] = Field(default=None, description="API key (GEMINI_API_KEY or OPENAI_API_KEY)")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    embedding_model: str = Field(default="text-embedding-3-small")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL for local/proxy")

    # Reasoning engine
    reasoning_enabled: bool = Field(default=True)
    reasoning_model: Optional[str] = Field(default=None, description="Model for complex reasoning (falls back to main model)")
    tool_calling_enabled: bool = Field(default=True)
    max_reasoning_steps: int = Field(default=10, ge=1, le=50)
    max_tool_calls_per_turn: int = Field(default=5, ge=1, le=20)
    stream_responses: bool = Field(default=True)
    summarization_enabled: bool = Field(default=True)
    summarization_threshold: int = Field(default=30, description="Summarize after N messages")

    # Personality
    personality: str = Field(default="professional", description="jarvis, professional, casual, academic")
    emotion_detection: bool = Field(default=True)
    response_style: str = Field(default="concise", description="concise, detailed, adaptive")


class VoiceSettings(BaseSettings):
    """Voice input/output configuration."""
    model_config = {"env_prefix": "VOICE_"}

    enabled: bool = Field(default=True)

    # Microphone
    mic_device_index: Optional[int] = Field(default=None, description="System mic device index (None = default)")
    mic_sample_rate: int = Field(default=16000, description="Microphone sample rate in Hz")
    mic_channels: int = Field(default=1, ge=1, le=2)
    mic_chunk_size: int = Field(default=1024, description="Frames per buffer for PyAudio")

    # Wake word
    wake_word_enabled: bool = Field(default=True)
    wake_word: str = Field(default="hey jarvis", description="Wake word phrase")
    wake_word_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)

    # Speech-to-text (Whisper)
    stt_engine: str = Field(default="whisper", description="STT engine: whisper, google, azure")
    whisper_model: str = Field(default="base", description="Whisper model: tiny, base, small, medium, large")
    whisper_language: str = Field(default="en")
    whisper_device: str = Field(default="cpu", description="Compute device: cpu, cuda")
    whisper_beam_size: int = Field(default=5, ge=1)
    whisper_fp16: bool = Field(default=False)

    # Text-to-speech
    tts_engine: str = Field(default="edge_tts", description="TTS engine: edge_tts, elevenlabs, pyttsx3")
    tts_voice_id: Optional[str] = Field(default="en-US-GuyNeural", description="TTS voice identifier")
    tts_rate: float = Field(default=1.0, ge=0.5, le=3.0, description="Speaking speed multiplier")
    tts_volume: float = Field(default=1.0, ge=0.0, le=2.0)
    tts_pitch: float = Field(default=0.0, description="Pitch adjustment in Hz")
    tts_output_sample_rate: int = Field(default=24000)

    # Voice personality presets
    tts_personality: str = Field(default="jarvis", description="Voice personality: jarvis, friday, friday_kid, british_butto")

    # Voice Activity Detection
    vad_enabled: bool = Field(default=True)
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Speech probability threshold")
    vad_speech_duration_ms: int = Field(default=300, description="Min speech duration to start capture")
    vad_silence_duration_ms: int = Field(default=800, description="Silence duration to end capture")
    vad_min_silence_ms: int = Field(default=500)
    vad_speech_pad_ms: int = Field(default=200)

    # Noise reduction
    noise_reduction_enabled: bool = Field(default=True)
    noise_reduction_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    noise_gate_threshold: float = Field(default=0.01, ge=0.0, le=1.0)

    # Conversation behavior
    continuous_listening: bool = Field(default=True, description="Keep listening after responses")
    interrupt_speech: bool = Field(default=True, description="Stop TTS when user starts speaking")
    max_record_seconds: int = Field(default=30, ge=1, le=120)
    silence_timeout_seconds: float = Field(default=1.5, ge=0.5, le=10.0)
    energy_threshold: float = Field(default=300, description="PyAudio energy threshold for silence detection")

    # Conversation logging
    voice_log_enabled: bool = Field(default=True)
    voice_log_dir: str = Field(default=str(BASE_DIR / "data" / "voice_logs"))
    voice_log_format: str = Field(default="json", description="json, csv, or txt")
    voice_log_audio: bool = Field(default=False, description="Save raw audio alongside transcripts")


class MemorySettings(BaseSettings):
    """Memory system configuration."""
    model_config = {"env_prefix": "MEMORY_"}

    enabled: bool = Field(default=True)

    # Storage paths
    data_dir: str = Field(default=str(BASE_DIR / "data" / "memory"))
    vector_store_path: str = Field(default=str(BASE_DIR / "data" / "memory" / "vectors"))
    backup_dir: str = Field(default=str(BASE_DIR / "data" / "memory" / "backups"))

    # Short-term memory
    short_term_enabled: bool = Field(default=True)
    short_term_max_items: int = Field(default=100, description="Max items in short-term buffer")
    short_term_max_messages: int = Field(default=50, description="Max messages in conversation buffer")
    short_term_summary_threshold: int = Field(default=30, description="Trigger summarization after N messages")
    conversation_window_size: int = Field(default=20, description="Number of recent messages for context")
    short_term_ttl_seconds: float = Field(default=3600, description="Time-to-live for short-term entries")

    # Long-term memory
    long_term_enabled: bool = Field(default=True)
    long_term_max_items: int = Field(default=10000)
    auto_save_interval: int = Field(default=30, description="Seconds between auto-saves")

    # Vector store
    vector_enabled: bool = Field(default=True)
    embedding_dimension: int = Field(default=1536)
    embedding_batch_size: int = Field(default=20)
    vector_index_type: str = Field(default="flat", description="flat, ivf, or hnsw")

    # User preferences
    preferences_enabled: bool = Field(default=True)
    preferences_file: str = Field(default=str(BASE_DIR / "data" / "memory" / "preferences.json"))

    # Project memory
    projects_enabled: bool = Field(default=True)
    projects_dir: str = Field(default=str(BASE_DIR / "data" / "memory" / "projects"))
    max_project_memories: int = Field(default=500)

    # Reminders
    reminders_enabled: bool = Field(default=True)
    reminders_file: str = Field(default=str(BASE_DIR / "data" / "memory" / "reminders.json"))
    reminder_check_interval: int = Field(default=60, description="Seconds between reminder checks")

    # Notes
    notes_enabled: bool = Field(default=True)
    notes_dir: str = Field(default=str(BASE_DIR / "data" / "memory" / "notes"))
    max_notes: int = Field(default=1000)

    # Conversation archive
    archive_enabled: bool = Field(default=True)
    archive_dir: str = Field(default=str(BASE_DIR / "data" / "memory" / "conversations"))
    max_archive_size: int = Field(default=10000, description="Max archived conversations")
    auto_archive_after_days: int = Field(default=7)

    # Importance scoring
    importance_enabled: bool = Field(default=True)
    importance_decay_rate: float = Field(default=0.01, description="Daily decay rate for importance")
    min_importance_threshold: float = Field(default=0.1, description="Minimum importance to keep")
    boost_repeated_access: float = Field(default=0.05, description="Importance boost per access")

    # Cleanup
    cleanup_enabled: bool = Field(default=True)
    cleanup_interval: int = Field(default=3600, description="Seconds between cleanup runs")
    max_total_memories: int = Field(default=50000)
    archive_before_delete: bool = Field(default=True)

    # Backup
    backup_enabled: bool = Field(default=True)
    backup_interval: int = Field(default=86400, description="Seconds between backups")
    max_backups: int = Field(default=7)

    # Search
    search_max_results: int = Field(default=20)
    search_min_relevance: float = Field(default=0.3, description="Minimum relevance score (0-1)")
    search_vector_weight: float = Field(default=0.6, description="Weight for vector similarity vs keyword")
    search_enable_hybrid: bool = Field(default=True)

    # Context injection
    context_injection_enabled: bool = Field(default=True)
    context_max_tokens: int = Field(default=2000, description="Max tokens for injected context")
    context_include_preferences: bool = Field(default=True)
    context_include_facts: bool = Field(default=True)
    context_include_recent: bool = Field(default=True)
    context_include_project: bool = True


class VisionSettings(BaseSettings):
    """Vision module configuration."""
    model_config = {"env_prefix": "VISION_"}

    # Core
    enabled: bool = Field(default=True)

    # Camera
    camera_enabled: bool = Field(default=False)
    camera_index: int = Field(default=0, description="Default camera device index")
    camera_width: int = Field(default=1280)
    camera_height: int = Field(default=720)
    camera_fps: int = Field(default=30)

    # Screen capture
    screen_capture_enabled: bool = Field(default=True)
    screenshot_interval: float = Field(default=1.0, description="Seconds between captures")
    screenshot_dir: str = Field(default="./data/screenshots/vision")

    # OCR
    ocr_enabled: bool = Field(default=True)
    ocr_engine: str = Field(default="easyocr", description="OCR engine: easyocr, tesseract, paddleocr")
    ocr_languages: list[str] = Field(default_factory=lambda: ["en"])

    # Object detection
    object_detection_enabled: bool = Field(default=True)
    object_detection_model: str = Field(default="yolov8n", description="YOLO model: yolov8n, yolov8s, yolov8m")
    object_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # Face detection
    face_detection_enabled: bool = Field(default=True)
    face_recognition_enabled: bool = Field(default=False)

    # Image understanding (LLM-based)
    image_understanding_enabled: bool = Field(default=True)
    image_understanding_model: str = Field(default="gpt-4o", description="Model for image analysis")

    # PDF reading
    pdf_enabled: bool = Field(default=True)
    pdf_max_pages: int = Field(default=50)

    # UI recognition
    ui_recognition_enabled: bool = Field(default=True)

    # Chart analysis
    chart_analysis_enabled: bool = Field(default=True)

    # Error recognition
    error_recognition_enabled: bool = Field(default=True)

    # Screen monitoring
    screen_monitor_enabled: bool = Field(default=True)
    screen_monitor_interval: float = Field(default=2.0, description="Monitor check interval in seconds")
    screen_monitor_change_threshold: float = Field(default=0.1, description="Minimum change ratio to trigger")

    # Paths
    models_dir: str = Field(default="./data/vision_models")
    cache_dir: str = Field(default="./data/vision_cache")


class AutomationSettings(BaseSettings):
    """Automation module configuration."""
    model_config = {"env_prefix": "AUTO_"}

    desktop_enabled: bool = Field(default=True)
    web_browser_enabled: bool = Field(default=True)
    file_ops_enabled: bool = Field(default=True)
    allowed_directories: list[str] = Field(
        default_factory=lambda: [str(Path.home())],
        description="Directories permitted for file operations"
    )

    # Safety
    safety_auto_approve_safe: bool = Field(default=True, description="Auto-approve safe actions")
    safety_auto_approve_moderate: bool = Field(default=True, description="Auto-approve moderate actions")
    safety_require_confirm_dangerous: bool = Field(default=True, description="Require confirmation for dangerous actions")
    safety_require_confirm_destructive: bool = Field(default=True, description="Require confirmation for destructive actions")

    # Application management
    apps_enabled: bool = Field(default=True)
    apps_common_dir: str = Field(default="", description="Additional directory for app discovery")

    # System control
    system_control_enabled: bool = Field(default=True)
    shutdown_confirm_prompt: bool = Field(default=True, description="Always confirm shutdown/restart")
    max_shutdown_delay: int = Field(default=3600, description="Maximum shutdown delay in seconds")

    # Screenshots
    screenshots_enabled: bool = Field(default=True)
    screenshots_dir: str = Field(default="./data/screenshots", description="Screenshot save directory")
    screenshots_max_count: int = Field(default=100, description="Max screenshots to keep")

    # Clipboard
    clipboard_enabled: bool = Field(default=True)
    clipboard_history_size: int = Field(default=50, description="Clipboard history entries to keep")

    # Keyboard/Mouse
    keyboard_mouse_enabled: bool = Field(default=True)
    keyboard_mouse_confirm_all: bool = Field(default=False, description="Confirm all keyboard/mouse actions")

    # Multi-monitor
    multi_monitor_enabled: bool = Field(default=True)

    # Process management
    process_manager_enabled: bool = Field(default=True)
    process_kill_requires_force: bool = Field(default=False, description="Require force flag to kill processes")


class BrowserSettings(BaseSettings):
    """Browser automation configuration (Playwright-based)."""
    model_config = {"env_prefix": "BROWSER_"}

    enabled: bool = Field(default=True)
    headless: bool = Field(default=False, description="Run browser in headless mode")
    slow_mo: int = Field(default=0, description="Slow down actions by ms (0 = normal speed)")
    timeout_ms: int = Field(default=30000, description="Default timeout for operations in ms")
    viewport_width: int = Field(default=1280)
    viewport_height: int = Field(default=720)

    # Paths
    user_data_dir: str = Field(default="./data/browser_profile", description="Persistent browser profile directory")
    downloads_dir: str = Field(default="./data/downloads", description="Download directory")
    screenshots_dir: str = Field(default="./data/screenshots/browser", description="Browser screenshot directory")

    # Browser config
    persistent_context: bool = Field(default=True, description="Use persistent browser context (keeps cookies/session)")
    chromium_channel: str = Field(default="chrome", description="Browser channel: chrome, msedge, chromium")
    proxy: str | None = Field(default=None, description="Proxy server URL (e.g., http://proxy:8080)")
    user_agent: str | None = Field(default=None, description="Custom user agent string")
    locale: str = Field(default="en-US")
    timezone_id: str = Field(default="America/New_York")
    ignore_https_errors: bool = Field(default=True)
    java_script_enabled: bool = Field(default=True)
    extra_http_headers: dict[str, str] = Field(default_factory=dict)
    blocked_domains: list[str] = Field(default_factory=list, description="Domains to block (ad blockers, etc.)")

    # Navigation
    navigation_enabled: bool = Field(default=True)
    default_wait_until: str = Field(default="domcontentloaded", description="Default wait condition: load, domcontentloaded, networkidle")

    # Interaction
    interaction_enabled: bool = Field(default=True)
    default_type_delay_ms: int = Field(default=50, description="Delay between keystrokes when typing")

    # Downloads
    downloads_enabled: bool = Field(default=True)
    max_downloads: int = Field(default=100, description="Max files to keep in downloads")

    # Auth
    auth_enabled: bool = Field(default=True)
    store_credentials: bool = Field(default=True, description="Save login credentials (base64 encoded)")
    credential_store_path: str = Field(default="./data/browser_profile/credentials.json")

    # Content extraction
    content_enabled: bool = Field(default=True)
    max_text_length: int = Field(default=50000, description="Max characters to extract from pages")

    # Monitoring
    monitor_enabled: bool = Field(default=True)
    default_watch_interval: int = Field(default=30, description="Default watch interval in seconds")
    max_concurrent_watches: int = Field(default=10)

    # Screenshots
    browser_screenshots_enabled: bool = Field(default=True)
    max_browser_screenshots: int = Field(default=200)


class APISettings(BaseSettings):
    """FastAPI server configuration."""
    model_config = {"env_prefix": "API_"}

    host: str = Field(default="0.0.0.0")
    port: int = Field(default_factory=lambda: int(os.environ.get("PORT", 8000)))
    reload: bool = Field(default=False)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_key: Optional[str] = Field(default=None, description="API authentication key")


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    model_config = {"env_prefix": "LOG_"}

    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    file_path: str = Field(default=str(BASE_DIR / "data" / "logs" / "jarvis.log"))
    max_bytes: int = Field(default=10_485_760)  # 10MB
    backup_count: int = Field(default=5)
    console_output: bool = Field(default=True)


class Settings(BaseSettings):
    """Root application settings aggregating all sub-configurations."""
    model_config = {"env_prefix": "JARVIS_", "env_file": ".env", "env_file_encoding": "utf-8"}

    app_name: str = "JARVIS"
    version: str = "0.1.0"
    debug: bool = Field(default=False)
    environment: str = Field(default="development", description="development, staging, production")

    ai: AISettings = Field(default_factory=AISettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @model_validator(mode="after")
    def resolve_api_key(self) -> "Settings":
        """Resolve API key from various environment variables."""
        import os
        # Check GEMINI_API_KEY first
        if not self.ai.api_key:
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if gemini_key:
                self.ai.api_key = gemini_key
                self.ai.provider = "gemini"
                self.ai.model = self.ai.model or "gemini-2.0-flash"
            else:
                # Fall back to OPENAI_API_KEY
                openai_key = os.environ.get("OPENAI_API_KEY")
                if openai_key:
                    self.ai.api_key = openai_key
                    self.ai.provider = "openai"
                    self.ai.model = self.ai.model or "gpt-4"
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton of application settings.

    Settings are loaded once from environment variables and the .env file,
    then cached for the lifetime of the process. Call `get_settings.cache_clear()`
    to force a reload.

    Returns:
        Settings: Validated application settings instance.
    """
    return Settings()
