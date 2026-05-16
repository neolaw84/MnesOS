from unittest.mock import MagicMock
from .shared import make_state, make_config, _DEFAULT_YARE_CONFIG
from MnesOS.graph.factory import build_graph

class TestBuildGraphFactory:
    """SRP: build_graph must be a standalone factory function in graph.py."""

    def test_build_graph_is_importable(self):
        assert callable(build_graph)

    def test_build_graph_monolithic_returns_compiled_app(self):
        app = build_graph(yare_config=_DEFAULT_YARE_CONFIG)
        assert hasattr(app, "invoke")
        assert hasattr(app, "get_graph")

    def test_build_graph_monolithic_has_all_expected_nodes(self):
        app = build_graph(yare_config=_DEFAULT_YARE_CONFIG)
        node_names = set(app.get_graph().nodes.keys())
        for expected in (
            "ResetAgentMessages", "CycleTick", "InputRouter", "Director",
            "PreTools", "Tools", "PostTools", "Narrator", "CleanupAgentMessages",
        ):
            assert expected in node_names, f"Missing expected node: {expected!r}"

    def test_build_graph_monolithic_excludes_lore_node(self):
        """Lore pre-node is replaced by the multi_lore_lookup tool."""
        app = build_graph(yare_config=_DEFAULT_YARE_CONFIG)
        node_names = set(app.get_graph().nodes.keys())
        assert "Lore" not in node_names

    def test_build_graph_monolithic_excludes_npc(self):
        app = build_graph(yare_config=_DEFAULT_YARE_CONFIG)
        node_names = set(app.get_graph().nodes.keys())
        assert "NPC_Brain" not in node_names

    def test_build_graph_accepts_all_llm_params(self):
        fake = MagicMock()
        app = build_graph(
            yare_config=_DEFAULT_YARE_CONFIG,
            llm_director=fake,
            llm_npc=fake,
            llm_narrator=fake,
        )
        assert hasattr(app, "invoke")

    def test_build_graph_dry_run_executes_a_turn(self):
        """build_graph with no LLMs must handle a full graph invocation without errors."""
        app = build_graph(yare_config=_DEFAULT_YARE_CONFIG)
        state = make_state()
        config = make_config()
        result = app.invoke(state, config=config)
        assert "bot_memory" in result
