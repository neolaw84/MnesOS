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
        if not isinstance(expr, str) or not expr.startswith("@"):
            return expr
        
        tree = ast.parse(expr[1:].strip(), mode='eval')
        return self._eval_node(tree.body, context or {})

    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Num): return node.n
        if isinstance(node, ast.Str): return node.s
        if isinstance(node, ast.Constant): return node.value
        
        if isinstance(node, ast.BinOp):
            return self.ALLOWED_OPERATORS[type(node.op)](
                self._eval_node(node.left, context),
                self._eval_node(node.right, context)
            )
        
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
        for step in event.get("steps", []):
            self._execute_step(step, inputs or {})
        self.call_depth -= 1

    def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]):
        action = step.get("action")
        
        if action == "set":
            val = self.evaluate(step["value"], context)
            self._set_path(step["var"], val)
            
        elif action == "mutate":
            val = self.evaluate(step["value"], context)
            curr = self._get_path(step["var"])
            op = step["op"]
            
            if op == "add": new_val = curr + val
            elif op == "sub": new_val = curr - val
            elif op == "mul": new_val = curr * val
            elif op == "div": new_val = curr / val
            
            # Enforce schema bounds
            schema = self._get_schema(step["var"])
            if schema:
                if "min" in schema: new_val = max(schema["min"], new_val)
                if "max" in schema: new_val = min(schema["max"], new_val)
                
            self._set_path(step["var"], new_val)

        elif action == "branch":
            for cond in step.get("conditions", []):
                if cond.get("else") or self.evaluate(cond.get("if"), context):
                    for substep in cond.get("steps", []):
                        self._execute_step(substep, context)
                    break

        elif action == "table_roll":
            result_val = self.evaluate(step["roll"], context)
            for key, val in step["table"].items():
                if self._match_range(key, result_val):
                    self._set_path(step["var"], val)
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

    def _set_path(self, path: str, value: Any):
        parts = path.split('.')
        root = parts[0]
        curr = self.state if root == "state" else self.temp
        for part in parts[1:-1]:
            curr = curr.setdefault(part, {})
        curr[parts[-1]] = value

    def _get_path(self, path: str) -> Any:
        parts = path.split('.')
        curr = self.state if parts[0] == "state" else self.temp
        for part in parts[1:]:
            curr = curr.get(part)
        return curr

    def _get_schema(self, path: str) -> Optional[Dict[str, Any]]:
        if not path.startswith("state."): return None
        parts = path.split('.')[1:]
        curr = self.config.get("state_schema", {})
        for part in parts:
            curr = curr.get(part)
        return curr if isinstance(curr, dict) and "type" in curr else None

    def _match_range(self, range_str: Union[str, int], value: int) -> bool:
        if isinstance(range_str, int): return value == range_str
        if '-' in range_str:
            low, high = map(int, range_str.split('-'))
            return low <= value <= high
        if range_str.endswith('+'):
            return value >= int(range_str[:-1])
        return value == int(range_str)
