"""Config validation module"""

from typing import Optional
from functools import lru_cache
from pydantic import AliasChoices, BaseModel, Field, RedisDsn, ValidationError, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class RedisConfig(BaseModel):
    encoding: str
    decode_responses: bool
    socket_connect_timeout: Optional[int] = None
    retry_on_timeout: Optional[bool] = None
    socket_timeout: Optional[int] = None

class RetryCfg(BaseModel):
    max_attempts: int
    mode: str

class BotoCoreCfg(BaseModel):
    connect_timeout: int = 3
    read_timeout: int = 5
    retries: RetryCfg = Field(default_factory=RetryCfg)


class BotoS3Config(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    verify: bool = True
    use_ssl: bool = True
    aws_session_token: Optional[str] = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    redis_url: RedisDsn = Field(
        "redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL"),
    )
    redis_config: RedisConfig = Field(
        {
            "encoding": "utf-8",
            "decode_responses": True,
        },
        validation_alias=AliasChoices("REDIS_CFG"),
    )
    s3_endpoint_url: HttpUrl = Field(
        "localhost:9000",
        validation_alias=AliasChoices("S3_URL")
    )
    s3_config: BotoS3Config = Field(
        ...,
        validation_alias=AliasChoices("S3_CFG")
    )
    s3_bucket: str = Field(
        ...,
        validation_alias=AliasChoices("S3_BUCKET")
    )
    boto3_config: BotoCoreCfg = Field(
        ...,
        validation_alias=AliasChoices("BOTO3_CFG")
    )


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        print(f"❌ Config validation error:\n{e}", flush=True)
        raise SystemExit(1)