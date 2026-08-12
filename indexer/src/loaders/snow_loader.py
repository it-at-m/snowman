import logging
from datetime import datetime

import requests
from langchain_core.documents import Document
from markdownify import markdownify

from src.config.settings import SnowSettings

logger = logging.getLogger(__name__)


class SnowLoader:
    """
    Loads published Knowledge Base articles from a ServiceNow instance using OAuth client_credentials.

    Config dictionary expected keys:
      - SERVICENOW_URL: Base URL of the ServiceNow instance, e.g. "https://example.service-now.com"
      - SERVICENOW_CLIENT_ID: OAuth client id
      - SERVICENOW_CLIENT_SECRET: OAuth client secret
      - SERVICENOW_OAUTH_SCOPE (optional): OAuth scopes, default knowledge
      - SERVICENOW_VERIFY_SSL (optional): bool, default True
      - SERVICENOW_PAGE_SIZE (optional): int, default 100

    Returned Documents have Markdown page_content and metadata including:
      - source: deep link to the KB article
      - updated_at: ISO formatted updated timestamp
      - title: short_description of the article
      - number: ServiceNow KB number
      - sys_id: sys_id of the KB article
    """

    def __init__(self, config: SnowSettings):
        self._base_url = config.servicenow_url.rstrip("/")
        self._client_id = config.servicenow_client_id
        self._client_secret = config.servicenow_client_secret
        self._scope = config.servicenow_oauth_scope
        self._verify_ssl = config.servicenow_verify_ssl
        self._page_size = config.servicenow_page_size
        self._languages = config.languages_list
        self._session = requests.Session()

    def _get_access_token(self) -> str:
        token_url = f"{self._base_url}/oauth_token.do"
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": self._scope,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        logger.debug("Requesting ServiceNow access token")
        resp = self._session.post(token_url, data=data, headers=headers, verify=self._verify_ssl)
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("ServiceNow OAuth response did not contain an access_token")
        return token

    @staticmethod
    def _parse_timestamp(value: str | None) -> str | None:
        if not value:
            return None
        # ServiceNow typically returns "YYYY-MM-DD HH:MM:SS"
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.isoformat()
        except ValueError:
            return value  # fallback to raw value if parsing fails

    def _fetch_articles(self) -> list[Document]:
        token = self._get_access_token()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
        )

        api_url = f"{self._base_url}/api/sn_km_api/knowledge/articles"
        offset = 0
        html_docs: list[Document] = []

        logger.info("Fetching ServiceNow KB articles")
        while True:
            logger.debug(f"Loading page {offset} with size {self._page_size}")
            params = {
                "filter": "workflow_state=published",
                "language": ",".join(self._languages),
                "fields": "text,workflow_state,language,kb_knowledge_base,sys_updated_on,sys_created_on,valid_to",
                "limit": str(self._page_size),
                "offset": str(offset),
            }
            resp = self._session.get(api_url, params=params, verify=self._verify_ssl)
            resp.raise_for_status()
            result = resp.json().get("result", [])
            articles = result.get("articles", [])

            if not articles:
                break

            for article in articles:
                sys_id = article.get("id")
                number = article.get("number")
                title = article.get("title")
                table_fields = article.get("fields")
                html_body = table_fields.get("text").get("value")
                lang = table_fields.get("language").get("value")
                kb = table_fields.get("kb_knowledge_base").get("display_value")
                created_raw = table_fields.get("sys_created_on").get("value")
                created_iso = self._parse_timestamp(created_raw)
                updated_raw = table_fields.get("sys_updated_on").get("value")
                updated_iso = self._parse_timestamp(updated_raw)

                # Construct a deep link to the article
                source_url = f"https://go.muenchen.de/sp/{number}"

                metadata = {
                    "title": title,
                    "number": number,
                    "sys_id": sys_id,
                    "lang": lang,
                    "knowledgebase": kb,
                    "created_at": created_iso,
                    "updated_at": updated_iso,
                    "source": source_url,
                }

                html_docs.append(Document(id=sys_id, page_content=html_body, metadata=metadata))

            offset += self._page_size

        return html_docs

    def load_documents(self) -> list[Document]:
        """Return the complete ServiceNow snapshot as canonical documents."""
        html_docs = self._fetch_articles()
        if not html_docs:
            logger.info("No ServiceNow KB articles found for the given configuration")
            return []

        # Convert HTML to Markdown
        markdown_docs = [
            Document(
                id=document.id,
                page_content=markdownify(document.page_content, heading_style="ATX"),
                metadata=document.metadata,
            )
            for document in html_docs
        ]

        logger.info(f"Loaded {len(html_docs)} ServiceNow KB articles as {len(markdown_docs)} documents")
        return markdown_docs

    def lazy_load(self) -> list[Document]:
        """Compatibility alias for callers using the LangChain loader convention."""
        return self.load_documents()
