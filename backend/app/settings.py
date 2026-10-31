from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://inventory:inventory_dev@localhost:5432/inventory"
    # Fail closed unless a local compose environment explicitly opts out.
    auth_disabled: bool = False
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    cors_origins: str = "http://localhost:5173"
    static_dir: str = "/app/static"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
