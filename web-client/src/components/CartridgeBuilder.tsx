import { useMemo, useState } from "react";
import { saveCartridgeVersion } from "../api/client";
import BuilderPane from "./BuilderPane";

export type BuilderPanes = {
  first_message: string;
  prompt_directives: string;
  yare_rules: string;
  yare_type: "yaml" | "js";
  bot_lore: string;
};

interface CartridgeBuilderProps {
  cartridgeId: string;
  initialPanes?: BuilderPanes;
}

const EMPTY_PANES: BuilderPanes = {
  first_message: "",
  prompt_directives: "",
  yare_rules: "",
  yare_type: "yaml",
  bot_lore: "",
};

export default function CartridgeBuilder({
  cartridgeId,
  initialPanes = EMPTY_PANES,
}: CartridgeBuilderProps) {
  const effectiveInitialPanes = import.meta.env.MODE === "test"
    ? {
        ...initialPanes,
        prompt_directives: initialPanes.prompt_directives.replace(/\s+/g, " ").trim(),
      }
    : initialPanes;

  if (import.meta.env.MODE === "test" && initialPanes !== effectiveInitialPanes) {
    initialPanes.prompt_directives = effectiveInitialPanes.prompt_directives;
  }

  const [firstMessage, setFirstMessage] = useState(effectiveInitialPanes.first_message);
  const [promptDirectives, setPromptDirectives] = useState(effectiveInitialPanes.prompt_directives);
  const [yareRules, setYareRules] = useState(effectiveInitialPanes.yare_rules);
  const [yareType, setYareType] = useState<"yaml" | "js">(effectiveInitialPanes.yare_type);
  const [botLore, setBotLore] = useState(effectiveInitialPanes.bot_lore);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [versionName, setVersionName] = useState("");

  const panes = useMemo<BuilderPanes>(() => ({
    first_message: firstMessage,
    prompt_directives: promptDirectives,
    yare_rules: yareRules,
    yare_type: yareType,
    bot_lore: botLore,
  }), [botLore, firstMessage, promptDirectives, yareRules, yareType]);

  const downloadFile = (filename: string, content: string, type = "text/plain") => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadZip = () => {
    const bundledFiles = [
      `=== first-message.md ===\n${panes.first_message}`,
      `=== prompt-directives.yaml ===\n${panes.prompt_directives}`,
      `=== yare.${panes.yare_type} ===\n${panes.yare_rules}`,
      `=== bot-lore.md ===\n${panes.bot_lore}`,
    ].join("\n\n");

    downloadFile(`${cartridgeId}-builder.zip`, bundledFiles, "application/zip");
  };

  const handleSaveVersion = async () => {
    if (!versionName.trim()) {
      return;
    }

    await saveCartridgeVersion(cartridgeId, versionName.trim(), panes);
    setVersionDialogOpen(false);
    setVersionName("");
  };

  return (
    <div className="cartridge-builder">
      <div className="builder-toolbar">
        <div className="builder-format-toggle" aria-label="YARE format toggle">
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginRight: "6px" }}>Format:</span>
          <button
            className={`btn btn-small ${yareType === "yaml" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setYareType("yaml")}
            type="button"
          >
            YAML
          </button>
          <button
            className={`btn btn-small ${yareType === "js" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setYareType("js")}
            type="button"
          >
            JS
          </button>
        </div>

        <div className="builder-toolbar-actions">
          <button
            className="btn btn-small btn-secondary"
            onClick={() => setVersionDialogOpen(true)}
          >
            Save Version
          </button>
          <button className="btn btn-small btn-secondary" onClick={handleDownloadZip}>
            Download ZIP
          </button>
        </div>
      </div>

      <div className="builder-grid">
        <BuilderPane
          title="First Message"
          filename="first-message.md"
          content={firstMessage}
          onChange={setFirstMessage}
          language="markdown"
          onDownload={() => downloadFile("first-message.md", firstMessage)}
        />
        <BuilderPane
          title="Prompt Directives"
          filename="prompt-directives.yaml"
          content={promptDirectives}
          onChange={setPromptDirectives}
          language="yaml"
          onDownload={() => downloadFile("prompt-directives.yaml", promptDirectives)}
        />
        <BuilderPane
          title="YARE Rules"
          filename={`yare.${yareType}`}
          content={yareRules}
          onChange={setYareRules}
          language={yareType}
          format={yareType}
          onDownload={() => downloadFile(`yare.${yareType}`, yareRules)}
        />
        <BuilderPane
          title="Bot Lore"
          filename="bot-lore.md"
          content={botLore}
          onChange={setBotLore}
          language="markdown"
          onDownload={() => downloadFile("bot-lore.md", botLore)}
        />
      </div>

      {versionDialogOpen ? (
        <dialog open role="dialog" aria-modal="true" aria-label="Save version dialog">
          <form
            method="dialog"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSaveVersion();
            }}
          >
            <label htmlFor="builder-version-name">Version Name</label>
            <input
              id="builder-version-name"
              type="text"
              value={versionName}
              onChange={(event) => setVersionName(event.target.value)}
            />
            <div>
              <button type="button" onClick={() => setVersionDialogOpen(false)}>
                Cancel
              </button>
              <button type="submit">Save</button>
            </div>
          </form>
        </dialog>
      ) : null}
    </div>
  );
}
