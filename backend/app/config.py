from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

ROOT = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore', hide_input_in_errors=True)
    app_env: Literal['production', 'development', 'test'] = 'production'
    database_url: str
    idempotency_secret: str = ''
    cookie_secure: bool = True
    allowed_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000'
    session_hours: int = 8
    default_timezone: str = 'Asia/Riyadh'
    default_currency: str = 'SAR'

    @model_validator(mode='after')
    def validate_database(self):
        if not self.database_url.startswith('mssql+pyodbc://') and not (
            self.app_env == 'test' and self.database_url.startswith('sqlite:///')
            and ':memory:' not in self.database_url
        ):
            raise ValueError('SQL Server is required. File SQLite is permitted only in APP_ENV=test.')
        if self.app_env == 'production' and not self.cookie_secure:
            raise ValueError('Production requires HTTPS and COOKIE_SECURE=true')
        if self.app_env != 'test' and len(self.idempotency_secret) < 32:
            raise ValueError('Set IDEMPOTENCY_SECRET to a random secret of at least 32 characters')
        if not 1 <= self.session_hours <= 24:
            raise ValueError('SESSION_HOURS must be 1..24')
        return self

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(',') if x.strip()]
