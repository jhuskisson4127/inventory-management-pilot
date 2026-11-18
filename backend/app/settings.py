from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://inventory:inventory_dev@localhost:3306/inventory?charset=utf8mb4"
    cors_origins: str = ""
    static_dir: str = "/app/static"
    session_cookie_secure: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
