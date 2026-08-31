import logging
from datetime import datetime
from urllib.parse import urlsplit

import requests
from langchain_core.documents import Document
from markdownify import markdownify

from src.config.settings import SnowSettings

logger = logging.getLogger(__name__)

ARTICLE_FIELDS = ",".join(
    [
        "kb_category",
        "kb_knowledge_base",
        "workflow_state",
        "sys_created_on",
        "sys_updated_on",
        "valid_to",
        "meta_description",
    ]
)


class SnowLoader:
    """Load all published ServiceNow KB articles as LangChain documents."""

    def __init__(self, config: SnowSettings):
        if not config.servicenow_url:
            raise ValueError("SERVICENOW_URL is required")
        if not config.servicenow_client_id or not config.servicenow_client_secret:
            raise ValueError("SERVICENOW_CLIENT_ID and SERVICENOW_CLIENT_SECRET are required")

        self._articles_url = config.servicenow_url
        self._token_url = config.token_url
        self._client_id = config.servicenow_client_id
        self._client_secret = config.servicenow_client_secret.strip()
        self._oauth_scope = config.servicenow_oauth_scope
        self._verify_ssl = config.servicenow_verify_ssl
        self._page_size = config.servicenow_page_size
        self._languages = config.languages_list
        self._session = requests.Session()
        self._session.proxies.update(config.proxies)

    @staticmethod
    def _field(fields: dict, name: str, display: bool = False):
        field = fields.get(name, {})
        if not isinstance(field, dict):
            return field
        key = "display_value" if display else "value"
        return field.get(key) or field.get("value")

    @staticmethod
    def _parse_timestamp(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").isoformat()
        except ValueError:
            return value

    @classmethod
    def _article_scope(cls, fields: dict) -> str:
        description = str(cls._field(fields, "meta_description") or "").lower()
        is_admin = "fachadministrator" in description
        is_user = "nutzer" in description
        if is_admin == is_user:
            return "general"
        return "admin" if is_admin else "user"

    def _get_access_token(self) -> str:
        logger.info("Authenticating with ServiceNow")
        response = self._session.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._oauth_scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=self._verify_ssl,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("ServiceNow OAuth response did not contain an access_token")
        logger.info("ServiceNow authentication succeeded")
        return token

    def _article_detail(self, article_id: str) -> dict:
        sys_id = article_id.split(":", 1)[-1]
        response = self._session.get(
            f"{self._articles_url.split('?', 1)[0].rstrip('/')}/{sys_id}",
            verify=self._verify_ssl,
        )
        response.raise_for_status()
        return response.json().get("result", {})

    def load_documents(self) -> list[Document]:
        """Return the complete published snapshot for the configured knowledge base."""
        logger.info("Starting ServiceNow knowledge article load")
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Accept": "application/json",
            }
        )

        documents: list[Document] = []
        offset = 0
        while True:
            logger.info("Fetching ServiceNow article page at offset %s", offset)
            params = {
                "filter": "workflow_state=published",
                "fields": ARTICLE_FIELDS,
                "limit": self._page_size,
                "offset": offset,
            }
            if self._languages:
                params["language"] = ",".join(self._languages)

            response = self._session.get(self._articles_url, params=params, verify=self._verify_ssl)
            response.raise_for_status()
            articles = response.json().get("result", {}).get("articles", [])
            if not articles:
                logger.info("No more ServiceNow articles found at offset %s", offset)
                break

            logger.info("Fetched %s ServiceNow article summaries", len(articles))

            for article in articles:
                fields = article.get("fields") or {}
                detail = self._article_detail(article["id"])
                sys_id = detail.get("sys_id") or article["id"].split(":", 1)[-1]
                number = detail.get("number") or article.get("number")
                title = detail.get("short_description") or article.get("title")
                content = detail.get("content") or ""

                source = article.get("link")
                if not source:
                    parts = urlsplit(self._articles_url)
                    source = f"{parts.scheme}://{parts.netloc}/kb?id=kb_article_view&sysparm_article={number}"

                documents.append(
                    Document(
                        id=sys_id,
                        page_content=markdownify(content, heading_style="ATX"),
                        metadata={
                            "title": title,
                            "number": number,
                            "sys_id": sys_id,
                            "language": detail.get("language"),
                            "knowledge_base": self._field(fields, "kb_knowledge_base", display=True),
                            "category": self._field(fields, "kb_category", display=True),
                            "created_at": self._parse_timestamp(self._field(fields, "sys_created_on")),
                            "updated_at": self._parse_timestamp(self._field(fields, "sys_updated_on")),
                            "valid_to": self._field(fields, "valid_to"),
                            "scope": self._article_scope(fields),
                            "attachments": detail.get("display_attachments") or [],
                            "source": source,
                        },
                    )
                )

            offset += len(articles)
            logger.info("Loaded %s ServiceNow articles so far", len(documents))

        logger.info("Loaded %s ServiceNow KB articles", len(documents))
        return documents

    def lazy_load(self):
        """Yield documents using the LangChain loader convention."""
        yield from self.load_documents()
