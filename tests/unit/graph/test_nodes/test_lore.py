from unittest.mock import patch, MagicMock
from ..shared import make_state, make_config
from MnesOS.graph.nodes.lore import context_retrieval_node

class TestContextRetrievalNode:
    def test_returns_retrieved_lore_key(self):
        state = make_state()
        config = make_config()
        result = context_retrieval_node(state, config)
        assert "retrieved_lore" in result

    def test_retrieved_lore_is_string(self):
        state = make_state()
        config = make_config()
        result = context_retrieval_node(state, config)
        assert isinstance(result["retrieved_lore"], str)

    def test_location_enriches_query(self):
        """Including a known location term should appear in the lore query."""
        state = make_state()
        state["bot_memory"]["current_location"] = "Crossroads"
        state["client_messages"] = [{"role": "user", "content": "I look at the crossroads."}]

        mock_store = MagicMock()
        mock_store.query.return_value = "Crossroads lore snippet."

        with patch("MnesOS.graph.nodes.lore.VectorLoreStore.from_file", return_value=mock_store):
            config = make_config(lore_content=None)
            result = context_retrieval_node(state, config)

        assert result["retrieved_lore"] != ""
        query_text = mock_store.query.call_args[0][0]
        assert "Crossroads" in query_text

    def test_npc_name_enriches_query(self):
        state = make_state()
        state["bot_memory"]["npc"] = {"name": "Goblin"}
        state["client_messages"] = [{"role": "user", "content": "I fight the goblin."}]
        config = make_config()
        result = context_retrieval_node(state, config)
        assert isinstance(result["retrieved_lore"], str)

    def test_completely_unrelated_query_returns_empty_or_string(self):
        state = make_state()
        state["client_messages"] = [{"role": "user", "content": "xyzzy frobozz quux zork"}]
        config = make_config()
        result = context_retrieval_node(state, config)
        # Must not raise; may be empty string
        assert isinstance(result["retrieved_lore"], str)

    def test_npc_template_name_mode_included_in_query(self):
        """NPC with a 'template' key (Name Mode) should be added to the query."""
        state = make_state()
        state["bot_memory"]["npc"] = {"name": "Mr_XYZ", "template": "Mr_XYZ"}
        state["client_messages"] = [{"role": "user", "content": "Hello."}]

        mock_store = MagicMock()
        mock_store.query.return_value = ""

        with patch("MnesOS.graph.nodes.lore.VectorLoreStore.from_file", return_value=mock_store):
            config = make_config(lore_content=None)
            context_retrieval_node(state, config)

        call_args = mock_store.query.call_args
        query_text = call_args[0][0]
        assert "Mr_XYZ" in query_text

    def test_npc_tags_list_all_included_in_query(self):
        """NPC with 'tags' list (Tag Mode) must have every tag in the query string."""
        state = make_state()
        state["bot_memory"]["npc"] = {"name": "Some NPC", "tags": ["orc", "shopkeeper"]}
        state["client_messages"] = [{"role": "user", "content": "Hello."}]

        mock_store = MagicMock()
        mock_store.query.return_value = ""

        with patch("MnesOS.graph.nodes.lore.VectorLoreStore.from_file", return_value=mock_store):
            config = make_config(lore_content=None)
            context_retrieval_node(state, config)

        call_args = mock_store.query.call_args
        query_text = call_args[0][0]
        assert "orc" in query_text
        assert "shopkeeper" in query_text

    def test_npc_multiple_tags_all_extracted(self):
        """All tags in the list should appear in query_text, not just the first."""
        state = make_state()
        state["bot_memory"]["npc"] = {"tags": ["orc", "shopkeeper", "veteran"]}
        state["client_messages"] = [{"role": "user", "content": "Trade."}]

        mock_store = MagicMock()
        mock_store.query.return_value = ""

        with patch("MnesOS.graph.nodes.lore.VectorLoreStore.from_file", return_value=mock_store):
            config = make_config(lore_content=None)
            context_retrieval_node(state, config)

        query_text = mock_store.query.call_args[0][0]
        assert "orc" in query_text
        assert "shopkeeper" in query_text
        assert "veteran" in query_text

    def test_legacy_archetype_species_keys_no_longer_used(self):
        """Old 'archetype' and 'species' keys should not be added to the query."""
        state = make_state()
        state["bot_memory"]["npc"] = {
            "archetype": "warrior",
            "species": "human",
        }
        state["client_messages"] = [{"role": "user", "content": "Fight."}]

        mock_store = MagicMock()
        mock_store.query.return_value = ""

        with patch("MnesOS.graph.nodes.lore.VectorLoreStore.from_file", return_value=mock_store):
            config = make_config(lore_content=None)
            context_retrieval_node(state, config)

        query_text = mock_store.query.call_args[0][0]
        assert "warrior" not in query_text
        assert "human" not in query_text

    def test_npc_without_template_or_tags_does_not_crash(self):
        """NPC data with neither template nor tags (e.g. only name) must not raise."""
        state = make_state()
        state["bot_memory"]["npc"] = {"name": "Goblin"}
        state["client_messages"] = [{"role": "user", "content": "Hello."}]
        config = make_config()
        result = context_retrieval_node(state, config)
        assert isinstance(result["retrieved_lore"], str)
