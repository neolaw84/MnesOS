from typing import Any, Dict, List, Optional
from .store import InterpreterStore
from .evaluator import YAREEvaluator
from .actions.core import InterpreterActions

MAX_CONTAINER_SIZE = 100
MAX_DICT_DEPTH = 3

class YAREInterpreter:
    """
    A secure, non-cyclic interpreter for the YAML Agentic Rules Engine (YARE).
    Handles deterministic state mutations and logic evaluation.
    
    Modularized into store, evaluator, and actions.
    """
    
    def __init__(self, config: Dict[str, Any], state: Dict[str, Any]):
        self._config = config
        self.state = state
        self.notes: List[str] = []
        self.temp: Dict[str, Any] = {}
        self.call_depth = 0
        self.max_call_depth = 10
        
        # Internal modules
        self.store = InterpreterStore(config, state)
        self.store.temp = self.temp  # Link temp storage
        self.evaluator = YAREEvaluator(self.store)
        self.actions = InterpreterActions(self)


    def evaluate(self, expr: Any, context: Dict[str, Any] = None) -> Any:
        return self.evaluator.evaluate(expr, context)

    def run_event(self, event_name: str, inputs: Dict[str, Any] = None):
        if self.call_depth > self.max_call_depth:
            self.notes.append("SYSTEM: Max event call depth reached. Halting.")
            return

        event = self.config.get("events", {}).get(event_name)
        if not event: return

        self.call_depth += 1

        coerced = dict(inputs or {})
        input_schema = event.get("inputs", {})
        if isinstance(input_schema, dict):
            for key, spec in input_schema.items():
                if key in coerced:
                    coerce_fn = self.store._TYPE_COERCIONS.get(spec.get("type", ""))
                    if coerce_fn is not None:
                        try:
                            coerced[key] = coerce_fn(coerced[key])
                        except (ValueError, TypeError):
                            pass
                    # Enum enforcement
                    if "enum" in spec:
                        allowed = [str(v).lower() for v in spec["enum"]]
                        val = coerced[key]
                        if isinstance(val, str): val = val.lower()
                        if val in allowed:
                            coerced[key] = val
                        elif "default" in spec:
                            coerced[key] = spec["default"]
                elif "default" in spec:
                    coerced[key] = spec["default"]

        context = {
            "state": self.state,
            "temp": self.temp,
            "inputs": coerced,
            "macros": self.config.get("macros", {}),
        }

        for step in event.get("steps", []):
            self.actions.execute_step(step, context)
        self.call_depth -= 1

    def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any] = None):
        """Internal bridge for backward compatibility with tests/internal calls."""
        return self.actions.execute_step(step, context or {})

    def _to_numeric(self, value: Any) -> Any:
        return self.store.to_numeric(value)

    def _get_path(self, path: str) -> Any:
        return self.store.get_path(path)

    def _set_path(self, path: str, value: Any):
        return self.store.set_path(path, value)

    def _dict_depth(self, d: Any) -> int:
        return self.store.dict_depth(d)

    def _eval_node(self, node: Any, context: Dict[str, Any] = None) -> Any:
        return self.evaluator._eval_node(node, context or {})

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value
        if hasattr(self, 'store'):
            self.store.config = value


__all__ = ["YAREInterpreter", "MAX_CONTAINER_SIZE", "MAX_DICT_DEPTH"]
