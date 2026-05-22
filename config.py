import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    public_url: str = "http://localhost:8000"
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", 8000))   # Railway sets PORT automatically
    secret_key: str = "change-this-secret"
    super_admin_email: str = "admin@yourdomain.com"
    super_admin_password: str = "changeme"

    # n8n webhook base URL (set in .env after installing n8n)
    # Example: https://your-n8n.railway.app/webhook
    n8n_webhook_base_url: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
