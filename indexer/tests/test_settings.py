import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError
from src.config.settings import IndexerSettings, SnowSettings


class IndexerSettingsTests(unittest.TestCase):
    def test_reads_sectioned_yaml_and_environment_overrides_it(self):
        yaml = """\
indexer:
  collection_name: yaml-collection
  document_chunk_size: 800
  document_chunk_overlap: 100
servicenow:
  servicenow_url: https://yaml.example.invalid/articles
  servicenow_languages: de,en
"""
        with TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.yaml"
            config_file.write_text(yaml, encoding="utf-8")
            environment = {
                "SNOWMAN_CONFIG_FILE": str(config_file),
                "VDB_COLLECTION_NAME": "environment-collection",
            }

            with patch.dict(os.environ, environment, clear=True):
                indexer = IndexerSettings(_env_file=None)
                servicenow = SnowSettings(_env_file=None)

        self.assertEqual("environment-collection", indexer.collection_name)
        self.assertEqual(800, indexer.document_chunk_size)
        self.assertEqual("https://yaml.example.invalid/articles", servicenow.servicenow_url)
        self.assertEqual(["de", "en"], servicenow.languages_list)

    def test_reads_shared_environment_aliases(self):
        settings = IndexerSettings(
            _env_file=None,
            VDB_COLLECTIONS="SNOW_KB",
            VDB_TIMEOUT="42",
            EMB_TIMEOUT="7",
        )
        self.assertEqual("SNOW_KB", settings.collection_name)
        self.assertEqual(42, settings.qdrant_timeout)
        self.assertEqual(7, settings.embedding_timeout)

    def test_rejects_multiple_collections_and_invalid_overlap(self):
        with self.assertRaises(ValidationError):
            IndexerSettings(_env_file=None, collection_name="one,two")
        with self.assertRaises(ValidationError):
            IndexerSettings(_env_file=None, document_chunk_size=100, document_chunk_overlap=100)

    def test_snow_languages_are_adapter_specific(self):
        settings = SnowSettings(
            _env_file=None,
            servicenow_url="https://example.invalid",
            servicenow_client_id="client",
            servicenow_client_secret="secret",
            servicenow_languages="de, en ",
        )
        self.assertEqual(["de", "en"], settings.languages_list)

    def test_snow_proxies_include_only_configured_protocols(self):
        settings = SnowSettings(
            _env_file=None,
            HTTP_PROXY="http://proxy.example.invalid:8080",
        )

        self.assertEqual({"http": "http://proxy.example.invalid:8080"}, settings.proxies)

    def test_snow_token_url_uses_instance_from_articles_endpoint(self):
        settings = SnowSettings(
            _env_file=None,
            servicenow_url="https://example.invalid/api/sn_km_api/knowledge/articles?kb=kb-id",
        )

        self.assertEqual("https://example.invalid/oauth_token.do", settings.token_url)


if __name__ == "__main__":
    unittest.main()
