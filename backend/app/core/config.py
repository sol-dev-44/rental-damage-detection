from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rental_damage"
    DATABASE_POOL_SIZE: int = 10

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "rental-damage-photos"
    R2_PUBLIC_URL: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours

    # AI thresholds
    MIN_CONFIDENCE_THRESHOLD: int = 70
    SIMILAR_CASES_LIMIT: int = 5

    # Photo constraints
    MAX_PHOTO_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp", "image/heic"]

    # Rate limiting
    API_RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def max_photo_size_bytes(self) -> int:
        return self.MAX_PHOTO_SIZE_MB * 1024 * 1024

    def get_r2_url(self, r2_key: str) -> str:
        """Construct a full URL from an R2 object key."""
        base = self.R2_PUBLIC_URL.rstrip("/")
        return f"{base}/{r2_key}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
