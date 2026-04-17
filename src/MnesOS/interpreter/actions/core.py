import operator
import re
from typing import Any, Dict, List, Union

class InterpreterActions:
    """Handles execution of individual YARE actions (set, mutate, branch, etc.)."""
    
    def __init__(self, interpreter):
        self.interp = interpreter

    def execute_step(self, step: Dict[str, Any], context: Dict[str, Any]):
        action = step.get("action")
        
        if action == "set":
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path, got {type(var).__name__}: {var!r}")
            val = self.interp.evaluate(step["value"], context)
            val = self.interp.store.coerce(val, var)
            self.interp.store.set_path(var, val)
            
        elif action == "mutate":
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path, got {type(var).__name__}: {var!r}")
            val = self.interp.evaluate(step["value"], context)
            curr = self.interp.store.get_path(var)
            if curr is None:
                raise ValueError(f"mutate: path {var!r} resolved to None")
            op = step["op"]
            _ops = {"add": operator.add, "sub": operator.sub, "mul": operator.mul, "div": operator.truediv}
            if op not in _ops:
                raise ValueError(f"mutate: unknown op {op!r}")
            new_val = _ops[op](curr, val)
            
            schema = self.interp.store.get_schema(var)
            if schema:
                if "min" in schema: new_val = max(schema["min"], new_val)
                if "max" in schema: new_val = min(schema["max"], new_val)
            new_val = self.interp.store.coerce(new_val, var)
            self.interp.store.set_path(var, new_val)

        elif action == "branch":
            for cond in step.get("conditions", []):
                if cond.get("else") or self.interp.evaluate(cond.get("if"), context):
                    for substep in cond.get("steps", []):
                        self.execute_step(substep, context)
                    break

        elif action == "table_roll":
            result_val = self.interp.evaluate(step["roll"], context)
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path")
            for key, val in step["table"].items():
                if self._match_range(key, result_val):
                    self.interp.store.set_path(var, self.interp.store.coerce(val, var))
                    break

        elif action == "call":
            args = {k: self.interp.evaluate(v, context) for k, v in step.get("args", {}).items()}
            self.interp.run_event(step["event"], args)

        elif action == "note":
            msg = step["message"]
            if "{" in msg:
                msg = re.sub(r'\{(.*?)\}', lambda m: str(self.interp.evaluate("@" + m.group(1), context)), msg)
            self.interp.notes.append(msg)
        
        elif action == "list_push":
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path")
            item = self.interp.evaluate(step.get("item") or step.get("value"), context)
            lst = self.interp.store.get_path(var)
            if lst is None: lst = []
            if not isinstance(lst, list):
                raise TypeError(f"list_push: path {var!r} not a list")
            from .. import MAX_CONTAINER_SIZE
            if len(lst) >= MAX_CONTAINER_SIZE:

                raise ValueError("list_push: MAX_CONTAINER_SIZE reached")
            self.interp.store.set_path(var, lst + [item])

        elif action == "list_remove":
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path")
            lst = self.interp.store.get_path(var)
            if lst is None: lst = []
            if not isinstance(lst, list):
                raise TypeError(f"list_remove: path {var!r} not a list")
            lst = list(lst)
            if "index" in step:
                idx = int(self.interp.evaluate(step["index"], context))
                if 0 <= idx < len(lst): lst.pop(idx)
            elif "value" in step:
                val = self.interp.evaluate(step["value"], context)
                if val in lst: lst.remove(val)
            self.interp.store.set_path(var, lst)

        elif action == "dict_set":
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path")
            key = self.interp.evaluate(step["key"], context)
            val = self.interp.evaluate(step["value"], context)
            d = self.interp.store.get_path(var)
            if d is None: d = {}
            if not isinstance(d, dict):
                raise TypeError(f"dict_set: path {var!r} not a dict")
            d = dict(d)
            d[key] = val
            from .. import MAX_CONTAINER_SIZE, MAX_DICT_DEPTH
            if self.interp.store.dict_depth(d) > MAX_DICT_DEPTH:

                raise ValueError("dict_set: MAX_DICT_DEPTH exceeded")
            if len(d) > MAX_CONTAINER_SIZE:
                raise ValueError("dict_set: MAX_CONTAINER_SIZE reached")
            self.interp.store.set_path(var, d)

        elif action == "dict_delete":
            var = self.interp.evaluate(step["var"], context)
            if not isinstance(var, str):
                raise TypeError(f"'var' must resolve to a string path")
            key = self.interp.evaluate(step["key"], context)
            d = self.interp.store.get_path(var)
            if d is None: d = {}
            if not isinstance(d, dict):
                raise TypeError(f"dict_delete: path {var!r} not a dict")
            d = dict(d)
            d.pop(key, None)
            self.interp.store.set_path(var, d)

        elif action == "foreach":
            array_expr = step.get("array")
            is_direct_state_path = (
                isinstance(array_expr, str)
                and array_expr.startswith(("state.", "temp."))
                and not array_expr.startswith("@")
            )
            if is_direct_state_path:
                array_val = self.interp.store.get_path(array_expr)
            else:
                array_val = self.interp.evaluate(array_expr, context)
            if array_val is None: return
            if not isinstance(array_val, list):
                raise TypeError("foreach array must resolve to a list")

            item_key = step.get("item", "item")
            index_key = step.get("index", "index")
            for idx, item in enumerate(array_val):
                iter_context = dict(context)
                iter_context[item_key] = item
                iter_context[index_key] = idx
                for substep in step.get("steps", []):
                    self.execute_step(substep, iter_context)

    def _match_range(self, range_str: Union[str, int], value: Any) -> bool:
        value = self.interp.store.to_numeric(value)
        if isinstance(range_str, int): return value == range_str
        if '-' in range_str:
            low, high = map(int, range_str.split('-'))
            return low <= value <= high
        if range_str.endswith('+'):
            return value >= int(range_str[:-1])
        return value == int(range_str)
