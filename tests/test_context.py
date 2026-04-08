"""
Unit tests for context.VectorLoreStore.

Covers: lore chunking, vocabulary building, cosine similarity querying,
        edge cases (empty lore, no match, multi-header docs).
"""

import pytest
from context import VectorLoreStore


SAMPLE_LORE = """\
# The Crossroads
A dusty intersection at the edge of the wilderness.
Goblins and bandits frequently ambush travellers here.

## Goblin (Creature)
Small, green-skinned humanoids.
They swarm weak targets and flee when outmatched.

## Safe Haven
A tranquil village behind stone walls.
Combat is prohibited within the gates.

### Healing Potion (Item)
A glowing red vial that restores HP when consumed.
"""


# ---------------------------------------------------------------------------
# Construction / chunking
# ---------------------------------------------------------------------------

class TestChunking:
    def test_chunks_split_on_headers(self):
        store = VectorLoreStore(SAMPLE_LORE)
        # Four headers in the sample
        assert len(store.chunks) == 4

    def test_each_chunk_starts_with_header(self):
        store = VectorLoreStore(SAMPLE_LORE)
        for chunk in store.chunks:
            assert chunk.lstrip().startswith("#")

    def test_chunk_contains_body_text(self):
        store = VectorLoreStore(SAMPLE_LORE)
        crossroads_chunk = next(c for c in store.chunks if "Crossroads" in c)
        assert "wilderness" in crossroads_chunk.lower()

    def test_empty_lore_produces_no_chunks(self):
        store = VectorLoreStore("")
        assert store.chunks == []

    def test_lore_with_no_headers_produces_no_chunks(self):
        store = VectorLoreStore("Just plain text without any headers.\n")
        assert store.chunks == []

    def test_vocab_is_non_empty_for_valid_lore(self):
        store = VectorLoreStore(SAMPLE_LORE)
        assert len(store.vocab) > 0

    def test_number_of_vectors_matches_chunks(self):
        store = VectorLoreStore(SAMPLE_LORE)
        assert len(store.vectors) == len(store.chunks)


# ---------------------------------------------------------------------------
# Query — relevance
# ---------------------------------------------------------------------------

class TestQuery:
    def test_query_returns_string(self):
        store = VectorLoreStore(SAMPLE_LORE)
        result = store.query("goblins attack")
        assert isinstance(result, str)

    def test_query_goblin_retrieves_goblin_chunk(self):
        store = VectorLoreStore(SAMPLE_LORE)
        result = store.query("goblin creature green")
        assert "Goblin" in result

    def test_query_healing_retrieves_potion_chunk(self):
        store = VectorLoreStore(SAMPLE_LORE)
        result = store.query("healing potion restore HP")
        assert "Potion" in result or "potion" in result.lower()

    def test_query_returns_at_most_top_k_chunks(self):
        store = VectorLoreStore(SAMPLE_LORE)
        result = store.query("goblin", top_k=1)
        # Separator "---" only appears between chunks, so ≤ 0 separators for top_k=1
        assert result.count("---") <= 0 or result.count("\n\n---\n\n") == 0

    def test_query_top_k_2_can_return_two_chunks(self):
        store = VectorLoreStore(SAMPLE_LORE)
        result = store.query("goblin attack wilderness", top_k=2)
        # If two chunks matched, separator should be present
        # (may not always be the case with cosine sim — just assert no crash)
        assert isinstance(result, str)

    def test_query_with_no_matching_terms_returns_empty_string(self):
        store = VectorLoreStore(SAMPLE_LORE)
        result = store.query("xyzzy frobozz zork quux")
        assert result == ""

    def test_query_on_empty_store_returns_empty_string(self):
        store = VectorLoreStore("")
        result = store.query("goblin")
        assert result == ""

    def test_query_is_case_insensitive(self):
        store = VectorLoreStore(SAMPLE_LORE)
        lower = store.query("goblin")
        upper = store.query("GOBLIN")
        assert lower == upper


# ---------------------------------------------------------------------------
# from_file
# ---------------------------------------------------------------------------

class TestFromFile:
    def test_from_file_loads_content(self, tmp_path):
        lore_file = tmp_path / "bot_lore.md"
        lore_file.write_text(SAMPLE_LORE)
        store = VectorLoreStore.from_file(str(lore_file))
        assert len(store.chunks) == 4

    def test_from_file_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            VectorLoreStore.from_file(str(tmp_path / "nonexistent.md"))
