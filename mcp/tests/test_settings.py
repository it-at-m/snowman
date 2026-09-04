import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError
from src.config.settings import McpSettings, RetrievalSettings


class McpSettingsTests(unittest.TestCase):
    def test_reads_yaml_and_environment_overrides_it(self) -> None:
        with TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.yaml"
            config_file.write_text("mcp:\n  port: 7000\n  log_level: WARNING\n", encoding="utf-8")
            environment = {"SNOWMAN_CONFIG_FILE": str(config_file), "MCP_PORT": "9000"}

            with patch.dict(os.environ, environment, clear=True):
                settings = McpSettings(_env_file=None)

        self.assertEqual(9000, settings.port)
        self.assertEqual("WARNING", settings.log_level)

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
    def test_reads_nested_retrieval_configuration_from_yaml(self) -> None:
        yaml = """\
retrieval:
  collections: articles, manuals
  filter_base_conditions:
    - field: metadata.tenant
      values: [munich]
  retrieval_tools:
    - name: search_manuals
      title: Search manuals
      description: Search the configured manuals.
      conditions:
        - field: metadata.topic
          values: [manual]
"""
        with TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.yaml"
            config_file.write_text(yaml, encoding="utf-8")

            with patch.dict(os.environ, {"SNOWMAN_CONFIG_FILE": str(config_file)}, clear=True):
                settings = RetrievalSettings(_env_file=None)

        self.assertEqual(["articles", "manuals"], settings.collections_list)
        self.assertEqual("metadata.tenant", settings.filter_base_conditions[0].field)
        self.assertEqual("search_manuals", settings.retrieval_tools[0].name)
        self.assertEqual("manual", settings.retrieval_tools[0].conditions[0].values[0])

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

    def test_default_scope_and_general_tool(self) -> None:
        settings = RetrievalSettings(_env_file=None)

        self.assertEqual("metadata.source_id", settings.filter_base_conditions[0].field)
        self.assertEqual(["snow-kb"], settings.filter_base_conditions[0].values)
        self.assertEqual("search_snow_knowledge_base", settings.retrieval_tools[0].name)
        self.assertEqual([], settings.retrieval_tools[0].conditions)

    def test_reads_json_scope_configuration_from_environment(self) -> None:
        base_conditions = [{"field": "metadata.tenant", "values": [" munich ", "munich", "shared"]}]
        tools = [
            {
                "name": "search_eakte_key_users",
                "title": "Search E-Akte key users",
                "description": " Search topic and audience. ",
                "conditions": [
                    {"field": "metadata.topic", "values": ["eakte"]},
                    {
                        "field": "metadata.knowledgebase",
                        "values": ["general", "key_user"],
                    },
                ],
            },
            {
                "name": "search_snow_knowledge_base",
                "title": "Search all SNOW knowledge",
                "description": "Search without a topic restriction.",
                "conditions": [],
            },
        ]
        environment = {
            "VDB_FILTER_BASE_CONDITIONS": json.dumps(base_conditions),
            "VDB_RETRIEVAL_TOOLS": json.dumps(tools),
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = RetrievalSettings(_env_file=None)

        self.assertEqual(["munich", "shared"], settings.filter_base_conditions[0].values)
        self.assertEqual("metadata.knowledgebase", settings.retrieval_tools[0].conditions[1].field)
        self.assertEqual(["general", "key_user"], settings.retrieval_tools[0].conditions[1].values)
        self.assertEqual("Search topic and audience.", settings.retrieval_tools[0].description)
        self.assertEqual([], settings.retrieval_tools[1].conditions)

    def test_rejects_empty_base_conditions_and_tools(self) -> None:
        with self.assertRaisesRegex(ValidationError, "base condition"):
            RetrievalSettings(_env_file=None, filter_base_conditions=[])

        with self.assertRaisesRegex(ValidationError, "retrieval tool"):
            RetrievalSettings(_env_file=None, retrieval_tools=[])

    def test_rejects_duplicate_tool_names_and_titles(self) -> None:
        duplicate_name = [
            {"name": "search_snow", "title": "First", "description": "First tool"},
            {"name": "search_snow", "title": "Second", "description": "Second tool"},
        ]
        with self.assertRaisesRegex(ValidationError, "names must be unique"):
            RetrievalSettings(_env_file=None, retrieval_tools=duplicate_name)

        duplicate_title = [
            {"name": "search_one", "title": " Same ", "description": "First tool"},
            {"name": "search_two", "title": "Same", "description": "Second tool"},
        ]
        with self.assertRaisesRegex(ValidationError, "titles must be unique"):
            RetrievalSettings(_env_file=None, retrieval_tools=duplicate_title)

    def test_rejects_invalid_or_empty_tool_text(self) -> None:
        invalid_tools = [
            {"name": "Search-SNOW", "title": "Search", "description": "Description"},
            {"name": "search_snow", "title": " ", "description": "Description"},
            {"name": "search_snow", "title": "Search", "description": " "},
        ]

        for tool in invalid_tools:
            with self.subTest(tool=tool), self.assertRaises(ValidationError):
                RetrievalSettings(_env_file=None, retrieval_tools=[tool])

    def test_rejects_empty_condition_fields_and_values(self) -> None:
        invalid_conditions = [
            {"field": " ", "values": ["snow-kb"]},
            {"field": "metadata.source_id", "values": []},
            {"field": "metadata.source_id", "values": [" "]},
        ]

        for condition in invalid_conditions:
            with self.subTest(condition=condition), self.assertRaises(ValidationError):
                RetrievalSettings(_env_file=None, filter_base_conditions=[condition])


if __name__ == "__main__":
    unittest.main()
