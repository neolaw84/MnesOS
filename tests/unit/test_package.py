"""Unit tests for the MnesOS package itself."""

import MnesOS


def test_version():
    """Verify package version is set (not empty/unknown)."""
    assert MnesOS.__version__ and MnesOS.__version__ != "unknown"


def test_placeholder():
    """Placeholder test — replace with real tests."""
    assert True
