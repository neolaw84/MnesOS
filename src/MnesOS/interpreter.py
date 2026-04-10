import ast
import operator
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

class YAREInterpreter:
    """
    A secure, non-cyclic interpreter for the YAML Agentic Rules Engine (YARE).
    Handles deterministic state mutations and logic evaluation.
    """
    
    _TYPE_COERCIONS: Dict[str, Any] = {
        "int":    int,
        "float":  float,
        "bool":   bool,
        "string": str,
    }

    ALLOWED_OPERATORS = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b, ast.Or: lambda a, b: a or b, ast.Not: operator.not_,
    }

    def __init__(self, config: Dict[str, Any], state: Dict[str, Any]):
        self.config = config
        self.state = state
        self.notes: List[str] = []
        self.temp: Dict[str, Any] = {}
        self.call_depth = 0
        self.max_call_depth = 10

    def evaluate(self, expr: Any, context: Dict[str, Any] = None) -> Any:
        """Evaluates a YARE expression string starting with '@'."""
        if not isinstance(expr, str):
            return expr
        # Bare single-quoted string literals without @ prefix: 'Safe Haven' -> Safe Haven
        if not expr.startswith("@"):
            stripped = expr.strip()
            if len(stripped) >= 2 and stripped[0] == "'" and stripped[-1] == "'":
                return stripped[1:-1]
            return expr

        import re as _re
        # Pre-process NdX dice notation so ast.parse accepts it: 1d20 -> '1d20'
        processed = _re.sub(r'(\d+d\d+)', r"'\1'", expr[1:].strip())
        tree = ast.parse(processed, mode='eval')
        return self._eval_node(tree.body, context or {})

    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Num): return node.n
        if isinstance(node, ast.Str): return node.s
        if isinstance(node, ast.Constant): return node.value

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            if isinstance(node.op, ast.USub): return -operand
            if isinstance(node.op, ast.UAdd): return +operand
            if isinstance(node.op, ast.Not): return not operand

        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v, context) for v in node.values]
            if isinstance(node.op, ast.And):
                result = True
                for v in values:
                    result = result and v
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for v in values:
                    result = result or v
                return result

        if isinstance(node, ast.BinOp):
            left  = self._eval_node(node.left,  context)
            right = self._eval_node(node.right, context)
            # For arithmetic operators, coerce operands to numeric — but only
            # when at least one side is already a number.  This handles LLM
            # event_args coming in as strings ("0" -> 0) or missing/semantic
            # values (None / "strength" -> 0) without breaking string
            # concatenation that also uses ast.Add (e.g. 'state.' + var + '.hp').
            if type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod):
                if isinstance(left, (int, float)) or isinstance(right, (int, float)):
                    left  = self._to_numeric(left)
                    right = self._to_numeric(right)
            return self.ALLOWED_OPERATORS[type(node.op)](left, right)
        
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op, right_node in zip(node.ops, node.comparators):
                right = self._eval_node(right_node, context)
                if not self.ALLOWED_OPERATORS[type(op)](left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.Attribute):
            # Handles state.player.stamina etc.
            parts = []
            curr = node
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            parts.reverse()
            
            # Resolve path
            root = parts[0]
            data = None
            if root == "state": data = self.state
            elif root == "temp": data = self.temp
            elif root == "inputs": data = context
            elif root == "macros": return self.evaluate(self.config.get("macros", {}).get(parts[1], ""))
            
            for part in parts[1:]:
                data = data.get(part)
            return data

        if isinstance(node, ast.Call):
            func_name = node.func.id
            args = [self._eval_node(a, context) for a in node.args]
            
            if func_name == "roll":
                # NdX notation parsing
                n, dx = map(int, args[0].lower().split('d'))
                return sum(random.randint(1, dx) for _ in range(n))
            if func_name == "timedelta":
                return timedelta(**{k.arg: self._eval_node(k.value, context) for k in node.keywords})
            if func_name == "time_delta":
                if len(args) != 2:
                    raise ValueError("time_delta expects exactly 2 arguments: time_delta(timestamp_a, timestamp_b)")
                t_a = self._parse_timestamp(args[0])
                t_b = self._parse_timestamp(args[1])
                return t_b - t_a
            if func_name == "abs": return abs(args[0])
            
        raise ValueError(f"Unsupported YARE expression node: {type(node)}")

    def run_event(self, event_name: str, inputs: Dict[str, Any] = None):
        """Executes a defined event DAG."""
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
                    coerce_fn = self._TYPE_COERCIONS.get(spec.get("type", ""))
                    if coerce_fn is not None:
                        try:
                            coerced[key] = coerce_fn(coerced[key])
                        except (ValueError, TypeError):
                            pass
                    # Enum enforcement: normalize case then fall back to default if invalid.
                    if "enum" in spec:
                        allowed = [str(v).lower() for v in spec["enum"]]
                        val = coerced[key]
                        if isinstance(val, str):
                            val = val.lower()
                        if val in allowed:
                            coerced[key] = val
                        elif "default" in spec:
                            coerced[key] = spec["default"]
                elif "default" in spec:
                    coerced[key] = spec["default"]

        for step in event.get("steps", []):
            self._execute_step(step, coerced)
        self.call_depth -= 1

    def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]):
        action = step.get("action")
        
        if action == "set":
            var = self.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path, got {type(var).__name__}: {var!r}")
            val = self.evaluate(step["value"], context)
            val = self._coerce(val, var)
            self._set_path(var, val)
            
        elif action == "mutate":
            var = self.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path, got {type(var).__name__}: {var!r}")
            val = self.evaluate(step["value"], context)
            curr = self._get_path(var)
            if curr is None:
                raise ValueError(f"mutate: path {var!r} resolved to None — cannot perform arithmetic")
            op = step["op"]
            _ops = {"add": operator.add, "sub": operator.sub, "mul": operator.mul, "div": operator.truediv}
            if op not in _ops:
                raise ValueError(f"mutate: unknown op {op!r}. Allowed: {list(_ops)}")
            new_val = _ops[op](curr, val)
            
            # Enforce schema bounds
            schema = self._get_schema(var)
            if schema:
                if "min" in schema: new_val = max(schema["min"], new_val)
                if "max" in schema: new_val = min(schema["max"], new_val)
            new_val = self._coerce(new_val, var)
            self._set_path(var, new_val)

        elif action == "branch":
            for cond in step.get("conditions", []):
                if cond.get("else") or self.evaluate(cond.get("if"), context):
                    for substep in cond.get("steps", []):
                        self._execute_step(substep, context)
                    break

        elif action == "table_roll":
            result_val = self.evaluate(step["roll"], context)
            var = self.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path, got {type(var).__name__}: {var!r}")
            for key, val in step["table"].items():
                if self._match_range(key, result_val):
                    self._set_path(var, self._coerce(val, var))
                    break

        elif action == "call":
            args = {k: self.evaluate(v, context) for k, v in step.get("args", {}).items()}
            self.run_event(step["event"], args)

        elif action == "note":
            msg = step["message"]
            # Simple interpolation
            if "{" in msg:
                import re
                msg = re.sub(r'\{(.*?)\}', lambda m: str(self.evaluate("@" + m.group(1), context)), msg)
            self.notes.append(msg)
        
        elif action == "foreach":
            array_expr = step.get("array")
            is_direct_state_path = (
                isinstance(array_expr, str)
                and array_expr.startswith(("state.", "temp."))
                and not array_expr.startswith("@")
            )
            if is_direct_state_path:
                array_val = self._get_path(array_expr)
            else:
                array_val = self.evaluate(array_expr, context)
            if array_val is None:
                return
            if not isinstance(array_val, list):
                raise TypeError(f"foreach array must resolve to a list, got {type(array_val).__name__}")

            item_key = step.get("item", "item")
            index_key = step.get("index", "index")
            for idx, item in enumerate(array_val):
                iter_context = dict(context)
                iter_context[item_key] = item
                iter_context[index_key] = idx
                for substep in step.get("steps", []):
                    self._execute_step(substep, iter_context)

    def _set_path(self, path: str, value: Any):
        parts = path.split('.')
        root = parts[0]
        curr = self.state if root == "state" else self.temp
        for part in parts[1:-1]:
            if part not in curr and part.lower() in curr:
                part = part.lower()
            curr = curr.setdefault(part, {})
        last = parts[-1]
        if last not in curr and last.lower() in curr:
            last = last.lower()
        curr[last] = value

    def _get_path(self, path: str) -> Any:
        parts = path.split('.')
        curr = self.state if parts[0] == "state" else self.temp
        for part in parts[1:]:
            if not isinstance(curr, dict):
                return None
            if part not in curr and part.lower() in curr:
                part = part.lower()
            curr = curr.get(part)
        return curr

    def _get_schema(self, path: str) -> Optional[Dict[str, Any]]:
        if not path.startswith("state."): return None
        parts = path.split('.')[1:]
        curr = self.config.get("state_schema", {})
        for part in parts:
            if not isinstance(curr, dict):
                return None
            curr = curr.get(part)
        return curr if isinstance(curr, dict) and "type" in curr else None

    def _to_numeric(self, value: Any) -> Any:
        """Coerce a value to a number for arithmetic.

        Called only when at least one sibling operand is already numeric,
        so string concatenation (both sides are strings) is never affected.

        Coercion rules:
        - int / float: returned as-is
        - None: returns 0  (missing LLM input treated as neutral modifier)
        - string that parses as int/float ("0", "3.5"): parsed
        - non-numeric string ("strength", "moderate"): returns 0
          (safe neutral; avoids crashing on semantic LLM values)
        """
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

    def _parse_timestamp(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise ValueError(f"Unsupported timestamp format for time_delta: {value!r}") from exc
        raise TypeError(f"time_delta only supports datetime, ISO timestamp string, int, or float, got {type(value).__name__}")

    def _coerce(self, value: Any, path: str) -> Any:
        """Coerce value to the schema-declared type for path, if declared."""
        schema = self._get_schema(path)
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

    def _match_range(self, range_str: Union[str, int], value: int) -> bool:
        if isinstance(range_str, int): return value == range_str
        if '-' in range_str:
            low, high = map(int, range_str.split('-'))
            return low <= value <= high
        if range_str.endswith('+'):
            return value >= int(range_str[:-1])
        return value == int(range_str)
