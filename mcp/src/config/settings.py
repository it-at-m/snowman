import os
import re
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
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


class RetrievalFilterCondition(BaseModel):
    """One exact-match condition applied to a Qdrant payload field."""

    field: str
    values: list[str]

    @field_validator("field")
    @classmethod
    def require_field(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("filter field must not be empty")
        return value

    @field_validator("values")
    @classmethod
    def require_values(cls, values: list[str]) -> list[str]:
        # dict keeps the configured order while removing duplicate exact matches.
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError("filter condition requires at least one value")
        return normalized


class RetrievalToolSettings(BaseModel):
    """Configuration used to register one scoped MCP search tool."""

    name: str
    title: str
    description: str
    conditions: list[RetrievalFilterCondition] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError(
                "retrieval tool name must start with a lowercase letter and contain only lowercase letters, numbers, and underscores"
            )
        return value

    @field_validator("title", "description")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("retrieval tool title and description must not be empty")
        return value


class McpSettings(YamlSettings):
    yaml_section = "mcp"
    # BaseSettings turns this class into configuration loaded from multiple sources.
    # Each class attribute below is both a typed setting and its default value.
    # At runtime Pydantic overrides these defaults with matching environment
    # variables and values from the .env file, then validates/coerces the result.
    model_config = SettingsConfigDict(
        # MCP_ means the field `port` is read from MCP_PORT, `path` from MCP_PATH,
        # and so on. This keeps server settings separate from retrieval settings.
        env_prefix="MCP_",
        # Load local development values from mcp/.env. Container deployments mostly
        # provide real environment variables instead; those take precedence.
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        # Ignore unrelated values in .env so the same file can contain settings for
        # other parts of the application without breaking validation here.
        extra="ignore",
        # Allow passing field names directly in tests or code, e.g. McpSettings(port=9090),
        # even though environment variables use the MCP_ prefix.
        populate_by_name=True,
    )

    transport: Literal["stdio", "streamable-http"] = "streamable-http"
    host: str = "0.0.0.0"
    port: int = 8080
    path: str = "/mcp"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    dns_rebinding_protection: bool = True
    allowed_hosts: str | None = None
    allowed_origins: str | None = None

    @property
    def allowed_hosts_list(self) -> list[str]:
        # The MCP server uses this list for DNS rebinding protection. Operators can
        # provide MCP_ALLOWED_HOSTS explicitly; otherwise we allow local access and,
        # when configured, the concrete bind host for this server instance.
        if self.allowed_hosts is not None:
            return _split_csv(self.allowed_hosts)

        hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        if self.host not in {"0.0.0.0", "127.0.0.1", "localhost"}:
            hosts.add(f"{self.host}:{self.port}")
        return sorted(hosts)

    @property
    def allowed_origins_list(self) -> list[str]:
        return _split_csv(self.allowed_origins or "")


class RetrievalSettings(YamlSettings):
    yaml_section = "retrieval"
    # Retrieval settings use BaseSettings as well, but without an env_prefix because
    # the consumed variables come from several existing namespaces: QDRANT_*, VDB_*,
    # OPENAI_*, and EMB_*. Field aliases below document those external names.
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    qdrant_url: str = "http://localhost:6333"
    qdrant_readonly_api_key: str | None = None
    # validation_alias maps legacy or deployment-specific environment variable names
    # to the Python field. AliasChoices accepts the first provided variable, so both
    # VDB_TIMEOUT and QDRANT_TIMEOUT can configure qdrant_timeout.
    qdrant_timeout: int = Field(default=10, validation_alias=AliasChoices("VDB_TIMEOUT", "QDRANT_TIMEOUT"))

    openai_embedding_model: str = "text-embedding-3-large"
    openai_api_base: str | None = None
    openai_api_key: str | None = None
    embedding_timeout: int = Field(default=10, validation_alias=AliasChoices("EMB_TIMEOUT", "EMBEDDING_TIMEOUT"))
    embedding_max_retries: int = Field(default=2, validation_alias=AliasChoices("EMB_MAX_RETRIES", "EMBEDDING_MAX_RETRIES"))

    sparse_embedding_model: str = Field(
        default="Qdrant/bm25",
        validation_alias=AliasChoices("EMB_SPARSE_MODEL", "VDB_SPARSE_EMBEDDING_MODEL"),
    )
    sparse_embedding_language: str = "german"
    fastembed_cache_path: str = "./model_cache"

    collections: str = Field(default="snow-search", validation_alias=AliasChoices("VDB_COLLECTIONS", "VDB_COLLECTION_NAME"))
    dense_vector_name: str = Field(default="dense", validation_alias="VDB_DENSE_VECTOR_NAME")
    sparse_vector_name: str = Field(default="sparse", validation_alias="VDB_SPARSE_VECTOR_NAME")
    # documents per collection
    retrieval_n_docs: int = Field(default=10, validation_alias="VDB_RETRIEVAL_N_DOCS")
    retrieval_score_threshold: float = Field(default=0.5, validation_alias="VDB_RETRIEVAL_SCORE_THRESHOLD")
    retrieval_fusion: Literal["DBSF", "RRF"] = Field(default="DBSF", validation_alias="VDB_RETRIEVAL_FUSION")
    # final documents returned to the agent
    retrieval_final_n_docs: int = Field(default=5, validation_alias="VDB_RETRIEVAL_FINAL_N_DOCS")

    filter_base_conditions: list[RetrievalFilterCondition] = Field(
        default_factory=lambda: [RetrievalFilterCondition(field="metadata.source_id", values=["snow-kb"])],
        validation_alias="VDB_FILTER_BASE_CONDITIONS",
    )
    retrieval_tools: list[RetrievalToolSettings] = Field(
        default_factory=lambda: [
            RetrievalToolSettings(
                name="search_snow_knowledge_base",
                title="Search SNOW knowledge base",
                description=(
                    "Search all generally available articles in the company SNOW "
                    "knowledge base. Use for questions that are not restricted to a "
                    "more specific configured domain."
                ),
            )
        ],
        validation_alias="VDB_RETRIEVAL_TOOLS",
    )

    rerank_enabled: bool = Field(default=False, validation_alias="VDB_RERANK_ENABLED")
    rerank_model: str = Field(default="cohere-rerank-v4.0-fast", validation_alias="RERANK_MODEL")

    @model_validator(mode="after")
    def validate_retrieval_scope(self) -> "RetrievalSettings":
        if not self.filter_base_conditions:
            raise ValueError("at least one retrieval base condition is required")
        if not self.retrieval_tools:
            raise ValueError("at least one retrieval tool is required")

        names = [tool.name for tool in self.retrieval_tools]
        if len(names) != len(set(names)):
            raise ValueError("retrieval tool names must be unique")

        titles = [tool.title for tool in self.retrieval_tools]
        if len(titles) != len(set(titles)):
            raise ValueError("retrieval tool titles must be unique")
        return self

    @property
    def collections_list(self) -> list[str]:
        return _split_csv(self.collections)


def _split_csv(value: str) -> list[str]:
    # Environment variables are always strings. For list-like settings we accept a
    # comma-separated string and convert it into a clean list for application code.
    return [item.strip() for item in value.split(",") if item.strip()]
