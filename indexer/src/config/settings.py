import os
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import AliasChoices, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class YamlSettings(BaseSettings):
    """Settings with an optional, sectioned YAML source."""

    yaml_section: ClassVar[str]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        configured_file = os.getenv("SNOWMAN_CONFIG_FILE")
        yaml_file = Path(configured_file) if configured_file else PROJECT_ROOT / "config.yaml"
        sources = (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
        if not yaml_file.is_file():
            if configured_file:
                raise FileNotFoundError(f"SNOWMAN_CONFIG_FILE does not exist: {yaml_file}")
            return sources
        return sources + (
            YamlConfigSettingsSource(
                settings_cls,
                yaml_file=yaml_file,
                yaml_config_section=cls.yaml_section,
            ),
        )


class IndexerSettings(YamlSettings):
    """Source-independent settings for the indexing pipeline."""

    yaml_section = "indexer"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )
    http_proxy: str | None = Field(default=None, validation_alias=AliasChoices("HTTP_PROXY", "VDB_HTTP_PROXY"))
    https_proxy: str | None = Field(default=None, validation_alias=AliasChoices("HTTPS_PROXY", "VDB_HTTPS_PROXY"))
    no_proxy: str | None = Field(default=None, validation_alias=AliasChoices("NO_PROXY", "VDB_NO_PROXY"))
    qdrant_url: str | None = Field(default=None, validation_alias=AliasChoices("VDB_URL", "QDRANT_URL"))
    qdrant_api_key: str | None = Field(default=None, validation_alias=AliasChoices("VDB_API_KEY", "QDRANT_API_KEY"))
    qdrant_timeout: int = Field(default=100, validation_alias=AliasChoices("VDB_TIMEOUT", "QDRANT_TIMEOUT"))
    collection_name: str = Field(default="snow-search", validation_alias=AliasChoices("VDB_COLLECTION_NAME", "VDB_COLLECTIONS"))
    openai_embedding_model: str = "text-embedding-3-large"
    openai_api_base: str | None = None
    openai_api_key: str | None = None
    embedding_timeout: int = Field(default=10, validation_alias=AliasChoices("EMB_TIMEOUT", "EMBEDDING_TIMEOUT"))
    embedding_max_retries: int = Field(default=2, validation_alias=AliasChoices("EMB_MAX_RETRIES", "EMBEDDING_MAX_RETRIES"))
    indexing_mode: Literal["dense", "hybrid"] = "hybrid"
    dense_vector_name: str = Field(default="dense", validation_alias="VDB_DENSE_VECTOR_NAME")
    sparse_vector_name: str = Field(default="sparse", validation_alias="VDB_SPARSE_VECTOR_NAME")
    sparse_embedding_model: str = Field(
        default="Qdrant/bm25", validation_alias=AliasChoices("EMB_SPARSE_MODEL", "VDB_SPARSE_EMBEDDING_MODEL")
    )
    sparse_embedding_language: str = "german"
    fastembed_cache_path: str = "./model_cache"
    document_chunk_size: int = Field(default=1_000, ge=1)
    document_chunk_overlap: int = Field(default=200, ge=0)
    indexing_batch_size: int = Field(default=20, ge=1)
    allow_empty_snapshot: bool = False

    @field_validator("collection_name")
    @classmethod
    def require_one_collection(cls, value: str) -> str:
        collection = value.strip()
        if not collection:
            raise ValueError("collection_name must not be empty")
        if "," in collection:
            raise ValueError("the indexer requires exactly one collection")
        return collection

    @field_validator("document_chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, value: int, info: ValidationInfo) -> int:
        chunk_size = info.data.get("document_chunk_size")
        if chunk_size is not None and value >= chunk_size:
            raise ValueError("document_chunk_overlap must be smaller than document_chunk_size")
        return value


class SnowSettings(YamlSettings):
    """Configuration owned by the example ServiceNow source adapter."""

    yaml_section = "servicenow"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )
    servicenow_url: str | None = Field(default=None, validation_alias=AliasChoices("SERVICENOW_URL", "SNOW_URL"))
    servicenow_client_id: str | None = Field(default=None, validation_alias=AliasChoices("SERVICENOW_CLIENT_ID", "SNOW_CLIENT_ID"))
    servicenow_client_secret: str | None = Field(
        default=None, validation_alias=AliasChoices("SERVICENOW_CLIENT_SECRET", "SNOW_CLIENT_SECRET")
    )
    servicenow_token_url: str | None = Field(default=None, validation_alias=AliasChoices("SERVICENOW_TOKEN_URL", "SNOW_TOKEN_URL"))
    servicenow_oauth_scope: str = "knowledge"
    servicenow_verify_ssl: bool = True
    servicenow_page_size: int = Field(default=100, ge=1)
    servicenow_languages: str = "de,en"
    http_proxy: str | None = Field(default=None, validation_alias=AliasChoices("HTTP_PROXY", "VDB_HTTP_PROXY"))
    https_proxy: str | None = Field(default=None, validation_alias=AliasChoices("HTTPS_PROXY", "VDB_HTTPS_PROXY"))

    @property
    def proxies(self) -> dict[str, str]:
        return {protocol: proxy for protocol, proxy in (("http", self.http_proxy), ("https", self.https_proxy)) if proxy}

    @property
    def languages_list(self) -> list[str]:
        return [language.strip() for language in self.servicenow_languages.split(",") if language.strip()]

    @property
    def token_url(self) -> str:
        if self.servicenow_token_url:
            return self.servicenow_token_url
        if not self.servicenow_url:
            return ""
        parts = urlsplit(self.servicenow_url)
        return urlunsplit((parts.scheme, parts.netloc, "/oauth_token.do", "", ""))
