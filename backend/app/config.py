from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, SecretStr
import base64
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./nyayavault.db"
    jwt_secret: str
    evidence_master_key: str
    jwt_expiry_minutes: int = 60
    storage_provider: str = "local"
    storage_path: str = "./data/evidence"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "evidence"
    minio_secure: bool = False
    blockchain_provider: str = "development"
    fabric_gateway_url: str = "http://127.0.0.1:4000"
    fabric_gateway_secret: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ai_provider: str = "disabled"
    gemini_api_key: SecretStr = SecretStr("")
    ai_model: str = "gemini-3.5-flash-lite"
    max_file_mb: int = 25
    @field_validator("jwt_secret")
    @classmethod
    def secret(cls,v):
        if len(v)<32: raise ValueError("JWT_SECRET requires at least 32 characters")
        return v
    @field_validator("evidence_master_key")
    @classmethod
    def key(cls,v):
        if len(base64.b64decode(v,validate=True)) !=32: raise ValueError("EVIDENCE_MASTER_KEY must encode 32 bytes")
        return v
settings=Settings()
