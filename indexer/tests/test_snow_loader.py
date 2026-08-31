import unittest
from unittest.mock import patch

from src.config.settings import SnowSettings
from src.loaders.snow_loader import SnowLoader


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def field(value, display_value=None):
    return {"value": value, "display_value": display_value or value}


class SnowLoaderTests(unittest.TestCase):
    def settings(self):
        return SnowSettings(
            _env_file=None,
            servicenow_url="https://example.invalid/api/sn_km_api/knowledge/articles?kb=kb-id",
            servicenow_client_id="client",
            servicenow_client_secret=" secret ",
            servicenow_page_size=2,
            servicenow_languages="de,en",
            http_proxy="http://proxy.example.invalid:8080",
            https_proxy="http://proxy.example.invalid:8443",
        )

    @patch("src.loaders.snow_loader.requests.Session")
    def test_loads_all_pages_as_documents(self, session_class):
        session = session_class.return_value
        session.headers = {}
        session.post.return_value = Response({"access_token": "token"})

        first_fields = {
            "meta_description": field("Dieser Artikel richtet sich an eAkte-Nutzer*innen."),
            "kb_knowledge_base": field("kb-id", "eAkte"),
            "kb_category": field("category-id", "Erste Schritte"),
            "sys_created_on": field("2026-08-01 10:00:00"),
            "sys_updated_on": field("2026-08-02 11:00:00"),
            "valid_to": field("2027-08-01"),
        }
        second_fields = {
            "meta_description": field("Allgemeine Information"),
            "kb_knowledge_base": field("kb-id", "eAkte"),
        }
        session.get.side_effect = [
            Response(
                {
                    "result": {
                        "articles": [
                            {
                                "id": "kb_knowledge:first-id",
                                "number": "KB001",
                                "title": "First",
                                "link": "https://example.invalid/article/KB001",
                                "fields": first_fields,
                            },
                            {
                                "id": "kb_knowledge:second-id",
                                "number": "KB002",
                                "title": "Second",
                                "fields": second_fields,
                            },
                        ]
                    }
                }
            ),
            Response(
                {
                    "result": {
                        "sys_id": "first-id",
                        "number": "KB001",
                        "short_description": "First article",
                        "content": "<h1>Heading</h1><p>Body</p>",
                        "language": "de",
                        "display_attachments": [{"file_name": "guide.pdf", "download_link": "https://example.invalid/guide.pdf"}],
                    }
                }
            ),
            Response(
                {
                    "result": {
                        "sys_id": "second-id",
                        "number": "KB002",
                        "short_description": "Second article",
                        "content": "<p>More content</p>",
                        "language": "en",
                        "display_attachments": [],
                    }
                }
            ),
            Response({"result": {"articles": []}}),
        ]

        documents = SnowLoader(self.settings()).load_documents()

        self.assertEqual(2, len(documents))
        self.assertEqual("first-id", documents[0].id)
        self.assertIn("# Heading", documents[0].page_content)
        self.assertEqual("user", documents[0].metadata["scope"])
        self.assertEqual("eAkte", documents[0].metadata["knowledge_base"])
        self.assertEqual("2026-08-02T11:00:00", documents[0].metadata["updated_at"])
        self.assertEqual("guide.pdf", documents[0].metadata["attachments"][0]["file_name"])
        self.assertEqual("general", documents[1].metadata["scope"])

        token_call = session.post.call_args
        self.assertEqual("https://example.invalid/oauth_token.do", token_call.args[0])
        self.assertEqual("secret", token_call.kwargs["data"]["client_secret"])
        session.proxies.update.assert_called_once_with(
            {
                "http": "http://proxy.example.invalid:8080",
                "https": "http://proxy.example.invalid:8443",
            }
        )
        list_calls = [call for call in session.get.call_args_list if "params" in call.kwargs]
        self.assertEqual([0, 2], [call.kwargs["params"]["offset"] for call in list_calls])
        self.assertIn("?kb=kb-id", list_calls[0].args[0])

    def test_assigns_user_admin_and_general_scopes(self):
        cases = {
            "Dieser Artikel richtet sich an eAkte-Nutzer*innen.": "user",
            "Dieser Artikel richtet sich an Fachadministrator*innen.": "admin",
            "Für Nutzer*innen und Fachadministrator*innen.": "general",
            "Allgemeine Information": "general",
            "": "general",
        }

        for description, expected in cases.items():
            with self.subTest(description=description):
                fields = {"meta_description": field(description)}
                self.assertEqual(expected, SnowLoader._article_scope(fields))

    @patch("src.loaders.snow_loader.requests.Session")
    def test_requires_access_token_in_oauth_response(self, session_class):
        session = session_class.return_value
        session.post.return_value = Response({})

        with self.assertRaisesRegex(RuntimeError, "access_token"):
            SnowLoader(self.settings()).load_documents()

    def test_requires_connection_settings(self):
        with self.assertRaisesRegex(ValueError, "SERVICENOW_URL"):
            SnowLoader(SnowSettings(_env_file=None))


if __name__ == "__main__":
    unittest.main()
