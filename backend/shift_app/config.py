from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore', hide_input_in_errors=True)
    app_env: Literal['production', 'development', 'test'] = 'production'
    database_url: str
    idempotency_secret: str = ''
    n8n_api_token: str = ''
    notification_channels: str = ''
    cookie_secure: bool = True
    allowed_origins: str = 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173'
    session_hours: int = 8
    default_timezone: str = 'Asia/Aden'
    store_name: str = 'سوبر ماركت بن دول'
    max_attachment_bytes: int = 5 * 1024 * 1024

    @model_validator(mode='after')
    def check_configuration(self):
        if not self.database_url.startswith('postgresql+psycopg://') and not (
            self.app_env == 'test' and self.database_url.startswith('sqlite:///')
            and ':memory:' not in self.database_url
        ):
            raise ValueError('Use PostgreSQL: postgresql+psycopg://. File SQLite is for tests only.')
        if len(self.idempotency_secret) < 32:
            raise ValueError('IDEMPOTENCY_SECRET requires at least 32 random characters')
        if self.app_env == 'production' and not self.cookie_secure:
            raise ValueError('Production requires HTTPS and COOKIE_SECURE=true')
        if self.notification_channels and len(self.n8n_api_token) < 32:
            raise ValueError('N8N_API_TOKEN requires at least 32 random characters')
        if any(x not in {'email', 'whatsapp'} for x in self.channels):
            raise ValueError('NOTIFICATION_CHANNELS must be email,whatsapp or empty')
        if not 1 <= self.session_hours <= 24:
            raise ValueError('SESSION_HOURS must be 1..24')
        ZoneInfo(self.default_timezone)
        return self

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(',') if x.strip()]

    @property
    def channels(self):
        return list(dict.fromkeys(x.strip() for x in self.notification_channels.split(',') if x.strip()))
