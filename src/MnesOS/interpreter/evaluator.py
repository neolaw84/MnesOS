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
            parts = []
            curr = node
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            parts.reverse()
            
            root = parts[0]
            if root == "macros":
                return self.evaluate(self.store.config.get("macros", {}).get(parts[1], ""))
            
            path = ".".join(parts)
            if root == "inputs":
                data = context
                for part in parts[1:]:
                    if not isinstance(data, dict): return None
                    data = data.get(part)
                return data

            return self.store.get_path(path)

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
