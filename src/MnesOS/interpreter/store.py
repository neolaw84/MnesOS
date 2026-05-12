from typing import Any, Dict, Optional, List
from datetime import datetime

class InterpreterStore:
    """Handles path-based access to state and temp variables, with schema-aware coercion."""
    
    _TYPE_COERCIONS: Dict[str, Any] = {
        "int":    int,
        "float":  float,
        "bool":   bool,
        "string": str,
    }

    def __init__(self, config: Dict[str, Any], state: Dict[str, Any]):
        self.config = config
        self.state = state
        self.temp: Dict[str, Any] = {}

    def _find_case_insensitive_key(self, d: Dict[str, Any], key: str) -> str:
        """Finds a key in dict d that matches 'key' case-insensitively. Returns original key if not found."""
        if key in d:
            return key
        key_lower = key.lower()
        for k in d:
            if k.lower() == key_lower:
                return k
        return key

    def get_path(self, path: str) -> Any:
        parts = path.split('.')
        curr = self.state if parts[0] == "state" else self.temp
        for part in parts[1:]:
            # If current is a list, try numeric index access
            if isinstance(curr, list):
                try:
                    idx = int(part)
                except Exception:
                    return None
                if idx < 0 or idx >= len(curr):
                    return None
                curr = curr[idx]
                continue

            if not isinstance(curr, dict):
                return None
            part = self._find_case_insensitive_key(curr, part)
            curr = curr.get(part)
        return curr

    def set_path(self, path: str, value: Any):
        parts = path.split('.')
        root = parts[0]
        curr = self.state if root == "state" else self.temp
        for part in parts[1:-1]:
            # If curr is a list and part is numeric, index into list and extend if needed
            if isinstance(curr, list):
                try:
                    idx = int(part)
                except Exception:
                    # cannot traverse non-numeric part on list
                    raise TypeError(f"Invalid path segment '{part}' for list")
                while idx >= len(curr):
                    curr.append({})
                curr = curr[idx]
                continue

            # curr is expected to be a dict here
            part_key = self._find_case_insensitive_key(curr, part)
            if part_key not in curr:
                curr[part_key] = {}
            curr = curr[part_key]

        last = parts[-1]
        # If setting into a list
        if isinstance(curr, list):
            try:
                idx = int(last)
            except Exception:
                raise TypeError(f"Invalid path segment '{last}' for list")
            while idx >= len(curr):
                curr.append(None)
            curr[idx] = value
            return

        last = self._find_case_insensitive_key(curr, last)
        curr[last] = value

    def get_schema(self, path: str) -> Optional[Dict[str, Any]]:
        if not path.startswith("state."): return None
        parts = path.split('.')[1:]
        curr = self.config.get("state_schema", {})
        for part in parts:
            if not isinstance(curr, dict):
                return None
            curr = curr.get(part)
        return curr if isinstance(curr, dict) and "type" in curr else None

    def coerce(self, value: Any, path: str) -> Any:
        schema = self.get_schema(path)
        if schema is None:
            return value
        coerce_fn = self._TYPE_COERCIONS.get(schema.get("type", ""))
        if coerce_fn is None:
            return value
        try:
            return coerce_fn(value)
        except (ValueError, TypeError) as exc:
            raise TypeError(
                f"Cannot coerce {value!r} to type {schema['type']!r} for path {path!r}: {exc}"
            ) from exc

    def dict_depth(self, d: Any) -> int:
        if not isinstance(d, dict) or not d:
            return 0
        return 1 + max(self.dict_depth(v) for v in d.values())

    def to_numeric(self, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return value
        if value is None:
            return 0
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
            try:
                return float(value)
            except ValueError:
                return 0
        return 0
