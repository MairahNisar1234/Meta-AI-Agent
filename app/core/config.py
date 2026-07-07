from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    openrouter_api_key: str
    tavily_api_key: str
    groq_api_key: str | None = None
    generated_agents_dir: str = "generated_agents"
    gemini_api_key: str = os.getenv("GEMINI_API_KEY")


    class Config:
        env_file = ".env"

settings = Settings()