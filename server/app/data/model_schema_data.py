"""Declarative scene, provider, protocol, and field definitions for the scene-driven AI model center.

All metadata the frontend needs to render the model center lives here.
Adding a new provider or scene should only touch this file.
"""

SCENES = [
    {
        "key": "script_generation",
        "label": "LLM · 脚本生成",
        "model_type": "llm",
        "description": "用于导演分镜、旁白、标题、提示词生成",
        "providers": ["bailian", "deepseek", "openai", "anthropic", "custom"],
        "fields": [
            {"key": "temperature", "label": "Temperature", "type": "number", "default": 0.7, "min": 0, "max": 2, "step": 0.1},
            {"key": "max_tokens", "label": "Max Tokens", "type": "number", "default": 4096, "min": 1, "max": 131072},
            {"key": "thinking_enabled", "label": "Thinking Enabled", "type": "boolean", "default": False},
            {"key": "thinking_budget", "label": "Thinking Budget", "type": "number", "default": 8192, "min": 1024, "max": 32000},
        ],
    },
    {
        "key": "llm_agency_expert_review",
        "label": "LLM · 专家团队审阅",
        "model_type": "llm",
        "description": "用于专家团队审阅、质量门禁和修复建议生成",
        "providers": ["bailian", "openai", "openai-compatible"],
        "fields": [
            {"key": "temperature", "label": "Temperature", "type": "number", "default": 0.2, "min": 0, "max": 2, "step": 0.1},
            {"key": "max_tokens", "label": "Max Tokens", "type": "number", "default": 8192, "min": 1, "max": 131072},
            {"key": "protocol", "label": "Protocol", "type": "select", "default": "openai_chat_completions", "options": ["openai_chat_completions"]},
        ],
    },
    {
        "key": "image_generation",
        "label": "Image · 画面生成",
        "model_type": "image",
        "description": "用于风格锁定参考图和 L0 图像资源生成",
        "providers": ["seedance", "qwen-image", "openai", "comfyui", "pixelle", "custom"],
        "fields": [
            {"key": "default_size", "label": "Default Size", "type": "select", "default": "1024x1024", "options": ["512x512", "1024x1024", "1024x1792", "1792x1024", "1440x2560", "2560x1440"]},
            {"key": "default_quality", "label": "Quality", "type": "select", "default": "hd", "options": ["standard", "hd"]},
        ],
    },
    {
        "key": "image_editing",
        "label": "Image · 以图改图",
        "model_type": "image",
        "description": "用于以图改图、多参考图生成、图集生成和图像修复工作流",
        "providers": ["seedance", "qwen-image", "openai", "comfyui", "pixelle", "custom"],
        "fields": [
            {"key": "default_size", "label": "Default Size", "type": "select", "default": "3K", "options": ["2K", "3K", "4K", "2048x2048", "1600x2848", "2304x4096"]},
            {"key": "default_quality", "label": "Quality", "type": "select", "default": "hd", "options": ["standard", "hd"]},
            {"key": "edit_strength", "label": "Edit Strength", "type": "number", "default": 0.65, "min": 0, "max": 1, "step": 0.05},
            {"key": "preserve_subject", "label": "Preserve Subject", "type": "boolean", "default": True},
            {"key": "supports_stream", "label": "Supports Stream", "type": "boolean", "default": False},
            {"key": "supports_image_set", "label": "Supports Image Set", "type": "boolean", "default": True},
            {"key": "max_reference_images", "label": "Max Reference Images", "type": "number", "default": 14, "min": 1, "max": 14},
            {"key": "max_output_images", "label": "Max Output Images", "type": "number", "default": 15, "min": 1, "max": 15},
            {"key": "supported_output_formats", "label": "Supported Output Formats", "type": "string", "default": "jpeg,png"},
            {"key": "supports_watermark_toggle", "label": "Supports Watermark Toggle", "type": "boolean", "default": True},
        ],
    },
    {
        "key": "video_rendering",
        "label": "Video · 视频渲染",
        "model_type": "video",
        "description": "用于 L4 视频生成和 Seedance 独立面板",
        "providers": ["seedance", "wan", "kling", "custom"],
        "fields": [
            {"key": "default_resolution", "label": "Default Resolution", "type": "select", "default": "720p", "options": ["720p", "1080p"]},
            {"key": "default_duration", "label": "Default Duration (s)", "type": "number", "default": 5, "min": 1, "max": 60},
            {"key": "default_aspect_ratio", "label": "Aspect Ratio", "type": "select", "default": "9:16", "options": ["16:9", "9:16", "1:1"]},
            {"key": "poll_interval_seconds", "label": "Poll Interval (s)", "type": "number", "default": 10, "min": 1, "max": 60},
            {"key": "poll_timeout_seconds", "label": "Poll Timeout (s)", "type": "number", "default": 180, "min": 30, "max": 600},
        ],
    },
    {
        "key": "video_composition",
        "label": "Compose - final video composition",
        "model_type": "video",
        "description": "Used for final L5 video composition and delivery writeback",
        "providers": ["pixelle", "custom"],
        "fields": [
            {"key": "default_resolution", "label": "Default Resolution", "type": "select", "default": "1080p", "options": ["720p", "1080p"]},
            {"key": "default_aspect_ratio", "label": "Aspect Ratio", "type": "select", "default": "9:16", "options": ["16:9", "9:16", "1:1"]},
        ],
    },
    {
        "key": "tts_synthesis",
        "label": "TTS · 语音合成",
        "model_type": "tts",
        "description": "用于旁白音频和未来语音合成",
        "providers": ["edge-tts", "openai", "custom"],
        "fields": [
            {"key": "voice", "label": "Voice", "type": "string", "default": "zh-CN-XiaoxiaoNeural"},
            {"key": "speed", "label": "Speed", "type": "number", "default": 1.0, "min": 0.5, "max": 2.0, "step": 0.1},
        ],
    },
    {
        "key": "quality_audit",
        "label": "Audit · 质量审计",
        "model_type": "audit",
        "description": "用于图像/视频质量审计",
        "providers": ["bailian", "openai", "anthropic", "gemini", "custom"],
        "fields": [
            {"key": "max_tokens", "label": "Max Tokens", "type": "number", "default": 4096, "min": 1, "max": 131072},
        ],
    },
]

PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "default_base_url": "https://api.deepseek.com/v1", "protocol": "openai_compatible", "test_strategy": "list_models"},
    "openai": {"label": "OpenAI", "default_base_url": "https://api.openai.com/v1", "protocol": "openai_compatible", "test_strategy": "list_models"},
    "openai-compatible": {"label": "OpenAI Compatible", "default_base_url": "", "protocol": "openai_chat_completions", "test_strategy": "list_models"},
    "bailian": {"label": "Bailian Qwen LLM", "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "protocol": "openai_chat_completions", "test_strategy": "list_models"},
    "anthropic": {"label": "Anthropic", "default_base_url": "https://api.anthropic.com/v1/messages", "protocol": "anthropic", "test_strategy": "list_models"},
    "seedance": {"label": "Seedance 2.0", "default_base_url": "https://ark.cn-beijing.volces.com/api/plan/v3", "protocol": "ark_plan_v3", "test_strategy": "noop"},
    "qwen-image": {"label": "Bailian Qwen Image", "default_base_url": "https://dashscope.aliyuncs.com/api/v1", "protocol": "dashscope_multimodal_generation", "test_strategy": "list_models"},
    "wan": {"label": "Bailian Wan", "default_base_url": "https://dashscope.aliyuncs.com/api/v1", "protocol": "dashscope_async", "test_strategy": "list_models"},
    "kling": {"label": "Kling 3.0", "default_base_url": "", "protocol": "http_custom", "test_strategy": "noop"},
    "gemini": {"label": "Gemini", "default_base_url": "https://generativelanguage.googleapis.com/v1beta", "protocol": "gemini", "test_strategy": "list_models"},
    "comfyui": {"label": "ComfyUI", "default_base_url": "", "protocol": "local_service", "test_strategy": "noop"},
    "pixelle": {"label": "Pixelle", "default_base_url": "http://localhost:8500", "protocol": "http_custom", "test_strategy": "health_check", "test_path": "/health"},
    "edge-tts": {"label": "Edge TTS", "default_base_url": "", "protocol": "local_service", "test_strategy": "noop"},
    "custom": {"label": "Custom", "default_base_url": "", "protocol": None, "test_strategy": "health_check", "test_path": "/"},
}

PROTOCOLS = ["openai_compatible", "openai_chat_completions", "anthropic", "gemini", "ark_plan_v3", "dashscope_async", "dashscope_multimodal_generation", "http_custom", "local_service"]

CUSTOM_FIELD_POLICY = {
    "enabled": True,
    "allowed_types": ["string", "number", "boolean", "select", "secret"],
}


def scene_key_to_model_type(scene_key: str) -> str:
    """Map a scene_key to its model_type for registry lookups."""
    for scene in SCENES:
        if scene["key"] == scene_key:
            return scene["model_type"]
    raise ValueError(f"Unknown scene key: {scene_key}")


def get_schema() -> dict:
    """Returns the full schema the frontend needs to render the model center."""
    common_fields = [
        {"key": "name", "label": "模型名称", "type": "string", "required": True, "max_length": 100},
        {"key": "provider", "label": "提供商", "type": "select", "required": True, "options_source": "scene_providers"},
        {"key": "base_url", "label": "Base URL", "type": "string", "required": False, "max_length": 300},
        {"key": "api_key", "label": "API Key", "type": "secret", "required": False},
        {"key": "api_secret", "label": "API Secret", "type": "secret", "required": False},
        {"key": "model_name", "label": "Model Identifier", "type": "string", "required": False, "max_length": 100},
    ]
    return {
        "common_fields": common_fields,
        "scenes": SCENES,
        "providers": PROVIDERS,
        "protocols": PROTOCOLS,
        "custom_field_policy": CUSTOM_FIELD_POLICY,
    }
