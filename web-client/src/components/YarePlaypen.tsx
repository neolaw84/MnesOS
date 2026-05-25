import { useState, useCallback } from "react";

/**
 * YarePlaypen — A developer playground for writing and testing
 * JavaScript YARE rules against a mock game state using eval.
 *
 * The JS source stored here is kept as a reference for the cartridge
 * developer to resume editing/updating their cartridge.
 */
export function YarePlaypen() {
  const [jsCode, setJsCode] = useState("");
  const [mockState, setMockState] = useState('{"player": {"hp": 100}}');
  const [output, setOutput] = useState("");

  const handleRun = useCallback(() => {
    // Validate JSON state
    let state: unknown;
    try {
      state = JSON.parse(mockState);
    } catch {
      setOutput("Error: Invalid JSON in mock state input.");
      return;
    }

    // Execute JS code in a sandboxed eval
    try {
      // Create a function that receives `state` and executes the code
      // eslint-disable-next-line no-new-func
      const fn = new Function("state", `"use strict"; ${jsCode}`);
      const result = fn(state);
      const display =
        result !== undefined ? JSON.stringify(result, null, 2) : JSON.stringify(state, null, 2);
      setOutput(display);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setOutput(`Error: ${msg}`);
    }
  }, [jsCode, mockState]);

  return (
    <div className="yare-playpen">
      <div className="yare-playpen__editor-section">
        <label htmlFor="yare-js-editor">YARE JS Editor</label>
        <textarea
          id="yare-js-editor"
          aria-label="YARE JS Editor"
          value={jsCode}
          onChange={(e) => setJsCode(e.target.value)}
          placeholder="// Write your YARE JS rules here..."
          rows={10}
        />
      </div>

      <div className="yare-playpen__state-section">
        <label htmlFor="mock-state">Mock State</label>
        <textarea
          id="mock-state"
          aria-label="Mock State"
          value={mockState}
          onChange={(e) => setMockState(e.target.value)}
          placeholder='{"player": {"hp": 100}}'
          rows={5}
        />
      </div>

      <button onClick={handleRun} aria-label="Run">
        Run
      </button>

      <div className="yare-playpen__output-section">
        <label htmlFor="playpen-output">Output</label>
        <pre id="playpen-output" aria-label="Output">
          {output}
        </pre>
      </div>
    </div>
  );
}
