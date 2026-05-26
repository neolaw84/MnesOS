/**
 * LuckyConsole — "I'm Feeling Lucky" cartridge generation UI.
 *
 * [MnesOS-260525-08] Allows users to enter plain-English requirements
 * and generates a full 4-file cartridge via the builder backend.
 */

import { useState, useCallback } from "react";
import {
  generateCartridge,
  type GenerateCartridgeRequest,
  type GenerateCartridgeResponse,
} from "../api/cartridgeBuilder";

type Status = "idle" | "generating" | "done" | "error";

export default function LuckyConsole() {
  const [requirements, setRequirements] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<GenerateCartridgeResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleGenerate = useCallback(async () => {
    if (!requirements.trim()) return;
    setStatus("generating");
    setResult(null);
    setErrorMsg("");

    try {
      const body: GenerateCartridgeRequest = { requirements: requirements.trim() };
      const response = await generateCartridge(body);
      setResult(response);
      setStatus("done");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Generation failed";
      setErrorMsg(msg);
      setStatus("error");
    }
  }, [requirements]);

  return (
    <div className="lucky-console">
      <h2>I'm Feeling Lucky</h2>
      <p className="lucky-console-subtitle">
        Describe the game you want and we'll generate a complete cartridge.
      </p>

      <div className="lucky-console-input">
        <label htmlFor="lucky-requirements">Requirements</label>
        <textarea
          id="lucky-requirements"
          aria-label="Requirements"
          rows={6}
          placeholder="e.g. Create a noir detective RPG set in 1940s Chicago with investigation mechanics..."
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          disabled={status === "generating"}
        />
      </div>

      <button
        className="btn btn-primary lucky-console-btn"
        onClick={handleGenerate}
        disabled={!requirements.trim() || status === "generating"}
      >
        {status === "generating" ? "Generating…" : "I'm Feeling Lucky"}
      </button>

      {status === "generating" && (
        <div className="lucky-console-status" aria-live="polite">
          <p>Generating your cartridge… This may take a moment.</p>
        </div>
      )}

      {status === "error" && (
        <div className="lucky-console-error" role="alert">
          <p>Error: {errorMsg || "Generation failed. Please try again."}</p>
        </div>
      )}

      {status === "done" && result && (
        <div className="lucky-console-results">
          <h3>Generated Cartridge</h3>

          <details open>
            <summary>Bot Lore</summary>
            <pre className="lucky-console-pre">{result.bot_lore}</pre>
          </details>

          <details>
            <summary>First Message</summary>
            <pre className="lucky-console-pre">{result.first_message}</pre>
          </details>

          <details>
            <summary>Prompt Directives</summary>
            <pre className="lucky-console-pre">{result.prompt_directives}</pre>
          </details>

          <details>
            <summary>YARE Spec</summary>
            <pre className="lucky-console-pre">{result.yare_spec}</pre>
          </details>
        </div>
      )}
    </div>
  );
}
