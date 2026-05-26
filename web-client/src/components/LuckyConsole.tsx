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

export interface LuckyConsoleProps {
  onGenerated: (data: GenerateCartridgeResponse) => void;
  existingContent?: {
    bot_lore?: string;
    first_message?: string;
    prompt_directives?: string;
    yare_spec?: string;
  };
}

export default function LuckyConsole({
  onGenerated,
  existingContent,
}: LuckyConsoleProps) {
  const [requirements, setRequirements] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleGenerate = useCallback(async () => {
    if (!requirements.trim()) return;
    setStatus("generating");
    setErrorMsg("");

    try {
      const body: GenerateCartridgeRequest = {
        requirements: requirements.trim(),
        ...(existingContent ? { existing_content: existingContent } : {}),
      };
      const response = await generateCartridge(body);
      onGenerated(response);
      setStatus("done");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Generation failed";
      setErrorMsg(msg);
      setStatus("error");
    }
  }, [requirements, existingContent, onGenerated]);

  return (
    <div className="lucky-console">
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
    </div>
  );
}
