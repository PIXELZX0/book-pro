from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    default_provider: str = Field(default="openai", alias="BOOK_PRO_PROVIDER")
    default_model: str = Field(default="gpt-4.1-mini", alias="BOOK_PRO_MODEL")
    max_chapters_per_request: int | None = Field(default=None, alias="BOOK_PRO_MAX_CHAPTERS")
    chapter_parallel: int = Field(default=3, alias="BOOK_PRO_CHAPTER_PARALLEL")
    output_dir: str = Field(default="books", alias="BOOK_PRO_OUTPUT_DIR")
    qwen_tts_api_key: str = Field(default="", alias="BOOK_PRO_QWEN_TTS_API_KEY")
    qwen_tts_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="BOOK_PRO_QWEN_TTS_BASE_URL",
    )
    qwen_tts_model: str = Field(default="qwen3-tts-vc-2026-01-22", alias="BOOK_PRO_QWEN_TTS_MODEL")
    mcp_enabled: bool = Field(default=True, alias="BOOK_PRO_MCP_ENABLED")
    mcp_path: str = Field(default="/mcp", alias="BOOK_PRO_MCP_PATH")
    mcp_token: str = Field(default="", alias="BOOK_PRO_MCP_TOKEN")
    mcp_import_dir: str = Field(default="", alias="BOOK_PRO_MCP_IMPORT_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
