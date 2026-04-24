import ast
import operator
import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

class YAREEvaluator:
    """Handles AST-based expression evaluation for YARE."""
    
    ALLOWED_OPERATORS = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b, ast.Or: lambda a, b: a or b, ast.Not: operator.not_,
    }

    def __init__(self, store):
        self.store = store

    def evaluate(self, expr: Any, context: Dict[str, Any] = None) -> Any:
        if not isinstance(expr, str):
            return expr
        if not expr.startswith("@"):
            stripped = expr.strip()
            if len(stripped) >= 2 and stripped[0] == "'" and stripped[-1] == "'":
                return stripped[1:-1]
            return expr

        processed = re.sub(r'(?<![\'"])(\b\d+d\d+\b)(?![\'"])', r"'\1'", expr[1:].strip())
        tree = ast.parse(processed, mode='eval')
        return self._eval_node(tree.body, context or {})

    def _eval_node(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        # Core Literals
        if isinstance(node, (ast.Num, ast.Str, ast.Bytes, ast.NameConstant, ast.Constant)):
            if isinstance(node, ast.Num): return node.n
            if isinstance(node, ast.Str): return node.s
            if isinstance(node, ast.Constant): return node.value
            if isinstance(node, ast.NameConstant): return node.value
            return getattr(node, 'value', None)

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
                    if not result: break
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for v in values:
                    result = result or v
                    if result: break
                return result

        if isinstance(node, ast.BinOp):
            left  = self._eval_node(node.left,  context)
            right = self._eval_node(node.right, context)
            if type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod):
                if isinstance(left, (int, float)) or isinstance(right, (int, float)):
                    left  = self.store.to_numeric(left)
                    right = self.store.to_numeric(right)
            return self.ALLOWED_OPERATORS[type(node.op)](left, right)
        
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op, right_node in zip(node.ops, node.comparators):
                right = self._eval_node(right_node, context)
                if not self.ALLOWED_OPERATORS[type(op)](left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.IfExp):
            test = self._eval_node(node.test, context)
            if test:
                return self._eval_node(node.body, context)
            else:
                return self._eval_node(node.orelse, context)

        if isinstance(node, ast.Attribute):
            # Special-case macros: macros.NAME -> evaluate macro string
            if isinstance(node.value, ast.Name) and node.value.id == "macros":
                macro_name = node.attr
                return self.evaluate(self.store.config.get("macros", {}).get(macro_name, ""))

            # Evaluate the base expression and then access attribute/key
            base = self._eval_node(node.value, context)
            if isinstance(base, dict):
                return base.get(node.attr)
            if isinstance(base, list):
                # attribute access on list is unsupported
                return None
            # Fallback to attribute access on objects
            try:
                return getattr(base, node.attr)
            except Exception:
                return None

        if isinstance(node, ast.Subscript):
            container = self._eval_node(node.value, context)
            # node.slice may be an expression; evaluate it
            try:
                index = self._eval_node(node.slice, context)
            except AttributeError:
                # older ASTs may wrap slice in ast.Index
                index = self._eval_node(node.slice.value, context)
            if isinstance(container, dict):
                return container.get(index)
            if isinstance(container, list):
                try:
                    idx = int(index)
                except Exception:
                    return None
                if idx < 0 or idx >= len(container):
                    return None
                return container[idx]
            return None

        if isinstance(node, ast.Dict):
            result = {}
            for k, v in zip(node.keys, node.values):
                key = self._eval_node(k, context) if k is not None else None
                val = self._eval_node(v, context)
                result[key] = val
            return result

        if isinstance(node, ast.List):
            return [self._eval_node(el, context) for el in node.elts]

        if isinstance(node, ast.Name):
            if node.id in context:
                return context[node.id]
            # Fallback for bare names that might be paths (unlikely in @ but for safety)
            return self.store.get_path(node.id)

        if isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else None
            args = [self._eval_node(a, context) for a in node.args]
            
            if func_name == "roll" and args:
                n, dx = map(int, args[0].lower().split('d'))
                return sum(random.randint(1, dx) for _ in range(n))
            if func_name == "timedelta":
                return timedelta(**{k.arg: self._eval_node(k.value, context) for k in node.keywords})
            if func_name == "time_delta" and len(args) == 2:
                t_a = self._parse_timestamp(args[0])
                t_b = self._parse_timestamp(args[1])
                return t_b - t_a
            if func_name == "abs" and args: return abs(args[0])
            
        raise ValueError(f"Unsupported YARE expression node: {type(node)}")

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
                raise ValueError(f"Unsupported timestamp format: {value!r}") from exc
        raise TypeError(f"time_delta unsupported type: {type(value).__name__}")
