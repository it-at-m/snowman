import unittest

from src.config.settings import McpSettings, RetrievalSettings


class McpSettingsTests(unittest.TestCase):
    def test_default_allowed_hosts_follow_port(self) -> None:
        settings = McpSettings(_env_file=None, port=9090)

        self.assertEqual(["127.0.0.1:9090", "localhost:9090"], settings.allowed_hosts_list)

    def test_allowed_hosts_and_origins_are_comma_separated(self) -> None:
        settings = McpSettings(
            _env_file=None,
            allowed_hosts="example.org, api.example.org ",
            allowed_origins="https://example.org, https://app.example.org ",
        )

        self.assertEqual(["example.org", "api.example.org"], settings.allowed_hosts_list)
        self.assertEqual(
            ["https://example.org", "https://app.example.org"],
            settings.allowed_origins_list,
        )


class RetrievalSettingsTests(unittest.TestCase):
    def test_collections_are_comma_separated(self) -> None:
        settings = RetrievalSettings(_env_file=None, collections="snow-search, docs ")

        self.assertEqual(["snow-search", "docs"], settings.collections_list)

    def test_reads_existing_vdb_environment_names(self) -> None:
        settings = RetrievalSettings(
            _env_file=None,
            VDB_COLLECTIONS="info,service",
            VDB_RETRIEVAL_N_DOCS="7",
            VDB_RETRIEVAL_SCORE_THRESHOLD="0.75",
            VDB_RETRIEVAL_FUSION="RRF",
        )

        self.assertEqual(["info", "service"], settings.collections_list)
        self.assertEqual(7, settings.retrieval_n_docs)
        self.assertEqual(0.75, settings.retrieval_score_threshold)
        self.assertEqual("RRF", settings.retrieval_fusion)


if __name__ == "__main__":
    unittest.main()
