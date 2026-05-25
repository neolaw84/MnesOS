"""
YARE JavaScript-to-YAML Static Compiler.

Compiles JavaScript YARE specifications into the standard YARE YAML
intermediate representation using a sandboxed JS evaluation approach.

The compiler uses Python's subprocess to run Node.js for evaluating the
JS module in a restricted context, extracting the exported `version`,
`state_schema`, `macros`, and `events` objects as JSON.

Design Decision: Since JS supports programmatic rule generation (loops,
helper functions, dynamic keys), a pure-AST parse would be insufficient.
We use a sandboxed Node.js eval that captures the module exports.
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict

logger = logging.getLogger(__name__)


class YareJSCompilationError(Exception):
    """Raised when a JavaScript YARE spec cannot be compiled."""
    pass


# The Node.js script that evaluates the JS module and extracts exports
_EVAL_SCRIPT = r"""
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const srcPath = process.argv[2];
const src = fs.readFileSync(srcPath, 'utf-8');

// Create a module-like sandbox
const _exp = {};
const _mod = { exports: _exp };

// Rewrite ES module syntax to CommonJS for vm evaluation
let code = src;
// Handle: export const X = ...;
code = code.replace(/export\s+const\s+(\w+)\s*=/g, '_exp.$1 =');
// Handle: export let X = ...;
code = code.replace(/export\s+let\s+(\w+)\s*=/g, '_exp.$1 =');
// Handle: export var X = ...;
code = code.replace(/export\s+var\s+(\w+)\s*=/g, '_exp.$1 =');
// Handle: export { X, Y, ... };
code = code.replace(/export\s*\{([^}]+)\}\s*;?/g, (match, names) => {
    return names.split(',').map(n => {
        const trimmed = n.trim();
        return `_exp.${trimmed} = ${trimmed};`;
    }).join('\n');
});
// Handle: export function X(...) {...}
code = code.replace(/export\s+function\s+(\w+)/g, '_exp.$1 = function $1');

const sandbox = {
    _exp,
    _mod,
    console: { log: () => {}, warn: () => {}, error: () => {} },
    JSON: JSON,
    Object: Object,
    Array: Array,
    Math: Math,
    String: String,
    Number: Number,
    Boolean: Boolean,
    parseInt: parseInt,
    parseFloat: parseFloat,
    undefined: undefined,
    null: null,
};

try {
    const script = new vm.Script(code, { filename: 'yare.js' });
    const context = vm.createContext(sandbox);
    script.runInContext(context, { timeout: 5000 });

    const result = {
        version: sandbox._exp.version || null,
        state_schema: sandbox._exp.state_schema || {},
        macros: sandbox._exp.macros || {},
        events: sandbox._exp.events || {},
    };

    // Validate version exists
    if (!result.version) {
        process.stderr.write('ERROR: Missing required "version" export');
        process.exit(1);
    }

    // Validate events is an object
    if (typeof result.events !== 'object' || Array.isArray(result.events)) {
        process.stderr.write('ERROR: "events" must be an object');
        process.exit(1);
    }

    // Validate state_schema is an object
    if (typeof result.state_schema !== 'object' || Array.isArray(result.state_schema)) {
        process.stderr.write('ERROR: "state_schema" must be an object');
        process.exit(1);
    }

    process.stdout.write(JSON.stringify(result));
} catch (e) {
    process.stderr.write('ERROR: ' + (e.message || String(e)));
    process.exit(1);
}
"""


def compile_js_to_yare(js_source: str) -> Dict[str, Any]:
    """
    Compile a JavaScript YARE specification to the standard YARE dict.

    Args:
        js_source: The raw JavaScript source code.

    Returns:
        A dict matching the YARE YAML structure with keys:
        version, state_schema, macros, events.

    Raises:
        YareJSCompilationError: If the JS cannot be parsed or evaluated.
    """
    if not js_source or not js_source.strip():
        raise YareJSCompilationError("Empty JavaScript source provided.")

    with tempfile.TemporaryDirectory() as tmpdir:
        js_path = os.path.join(tmpdir, "yare_input.js")
        eval_path = os.path.join(tmpdir, "eval_runner.js")

        # Write a package.json to force CommonJS mode in this directory
        pkg_path = os.path.join(tmpdir, "package.json")
        with open(pkg_path, "w", encoding="utf-8") as f:
            f.write('{"type": "commonjs"}')

        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_source)

        with open(eval_path, "w", encoding="utf-8") as f:
            f.write(_EVAL_SCRIPT)

        try:
            result = subprocess.run(
                ["node", eval_path, js_path],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmpdir,
            )
        except FileNotFoundError:
            raise YareJSCompilationError(
                "Node.js is not installed or not in PATH. "
                "Node.js is required for JS YARE compilation."
            )
        except subprocess.TimeoutExpired:
            raise YareJSCompilationError(
                "JS YARE compilation timed out (possible infinite loop)."
            )

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if error_msg.startswith("ERROR: "):
                error_msg = error_msg[7:]
            raise YareJSCompilationError(
                f"Compilation failed: {error_msg}"
            )

        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise YareJSCompilationError(
                f"Compilation produced invalid JSON output: {e}"
            )

    return parsed
