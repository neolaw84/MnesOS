import pytest
from MnesOS.interpreter import YAREInterpreter

def make_interp(state=None) -> YAREInterpreter:
    """Helper to instantiate an interpreter with an optional initial state."""
    return YAREInterpreter({}, state or {})
