from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # AI Provider Selection
    AI_PROVIDER: str = "auto"  # Options: "openai", "anthropic", "auto"
    
    # OpenAI API Settings
    OPENAI_API_KEY: str | None = None # Allow key to be optional to enable server startup
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_MODEL_CHEAT_CHECK: str = "qwen3-235b-a22b"
    
    # Anthropic API Settings
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str | None = None  # Optional, for custom endpoints
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"

    # JWT Settings for OAuth2
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 600

    # Database URL
    DATABASE_URL: str = "sqlite:///./veloera.db"

    # Linux.do OAuth Settings
    LINUXDO_CLIENT_ID: str | None = None
    LINUXDO_CLIENT_SECRET: str | None = None
    LINUXDO_SCOPE: str = "read"

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    UVICORN_RELOAD: bool = True

    # Admin Settings
    # Minimum trust level required to access admin APIs
    ADMIN_MIN_TRUST_LEVEL: int = 3
    # Optional comma-separated whitelist of admin usernames
    ADMIN_USER_WHITELIST: str | None = None

    # Point to the .env file in the 'backend' directory relative to the project root
    model_config = SettingsConfigDict(env_file="backend/.env")

# Create a single instance of the settings
settings = Settings()
