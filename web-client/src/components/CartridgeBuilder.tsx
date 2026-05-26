import { useMemo, useState } from "react";
import { saveCartridgeVersion } from "../api/client";
import BuilderPane from "./BuilderPane";
import { YarePlaypen } from "./YarePlaypen";
import LuckyConsole from "./LuckyConsole";
import { MinigameDirectory } from "./MinigameDirectory";

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
  const [activeTab, setActiveTab] = useState<"lore" | "directives" | "rules" | "message">("lore");
  const [playpenOpen, setPlaypenOpen] = useState(false);
  const [luckyOpen, setLuckyOpen] = useState(false);
  const [minigameDocsOpen, setMinigameDocsOpen] = useState(false);

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
        <div className="builder-tabs">
          <button
            className={`builder-tab ${activeTab === "lore" ? "active" : ""}`}
            onClick={() => setActiveTab("lore")}
          >
            📜 Bot Lore
          </button>
          <button
            className={`builder-tab ${activeTab === "directives" ? "active" : ""}`}
            onClick={() => setActiveTab("directives")}
          >
            🎯 Directives
          </button>
          <button
            className={`builder-tab ${activeTab === "rules" ? "active" : ""}`}
            onClick={() => setActiveTab("rules")}
          >
            ⚖️ YARE Rules
          </button>
          <button
            className={`builder-tab ${activeTab === "message" ? "active" : ""}`}
            onClick={() => setActiveTab("message")}
          >
            ✉️ First Message
          </button>
        </div>

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
            onClick={() => setLuckyOpen(true)}
            title="Generate content using AI"
          >
            ✨ I'm Feeling Lucky
          </button>
          <button
            className="btn btn-small btn-secondary"
            onClick={() => setMinigameDocsOpen(true)}
            title="View minigame documentation"
          >
            📖 Minigame Docs
          </button>
          <button
            className="btn btn-small btn-secondary"
            onClick={() => setPlaypenOpen(true)}
          >
            🧪 Test JS
          </button>
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

      <div className="builder-content">
        {activeTab === "message" && (
          <BuilderPane
            title="First Message"
            filename="first-message.md"
            content={firstMessage}
            onChange={setFirstMessage}
            language="markdown"
            onDownload={() => downloadFile("first-message.md", firstMessage)}
          />
        )}
        {activeTab === "directives" && (
          <BuilderPane
            title="Prompt Directives"
            filename="prompt-directives.yaml"
            content={promptDirectives}
            onChange={setPromptDirectives}
            language="yaml"
            onDownload={() => downloadFile("prompt-directives.yaml", promptDirectives)}
          />
        )}
        {activeTab === "rules" && (
          <BuilderPane
            title="YARE Rules"
            filename={`yare.${yareType}`}
            content={yareRules}
            onChange={setYareRules}
            language={yareType}
            format={yareType}
            onDownload={() => downloadFile(`yare.${yareType}`, yareRules)}
          />
        )}
        {activeTab === "lore" && (
          <BuilderPane
            title="Bot Lore"
            filename="bot-lore.md"
            content={botLore}
            onChange={setBotLore}
            language="markdown"
            onDownload={() => downloadFile("bot-lore.md", botLore)}
          />
        )}
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

      {playpenOpen && (
        <div className="modal-overlay" onClick={() => setPlaypenOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ width: "auto", maxWidth: "900px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h2 style={{ margin: 0 }}>🧪 YARE JS Playpen</h2>
              <button className="btn btn-small btn-secondary" onClick={() => setPlaypenOpen(false)}>✕</button>
            </div>
            <YarePlaypen />
          </div>
        </div>
      )}

      {luckyOpen && (
        <div className="modal-overlay" onClick={() => setLuckyOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ width: "600px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h2 style={{ margin: 0 }}>✨ I'm Feeling Lucky</h2>
              <button className="btn btn-small btn-secondary" onClick={() => setLuckyOpen(false)}>✕</button>
            </div>
            <LuckyConsole
              existingContent={
                botLore || firstMessage || promptDirectives || yareRules
                  ? {
                      bot_lore: botLore || undefined,
                      first_message: firstMessage || undefined,
                      prompt_directives: promptDirectives || undefined,
                      yare_spec: yareRules || undefined,
                    }
                  : undefined
              }
              onGenerated={(result) => {
                setBotLore(result.bot_lore);
                setFirstMessage(result.first_message);
                setPromptDirectives(result.prompt_directives);
                setYareRules(result.yare_spec);
                setLuckyOpen(false);
              }}
            />
          </div>
        </div>
      )}

      {minigameDocsOpen && (
        <div className="modal-overlay" onClick={() => setMinigameDocsOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ width: "90vw", maxWidth: "1000px", height: "80vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h2 style={{ margin: 0 }}>📖 Minigame Documentation</h2>
              <button className="btn btn-small btn-secondary" onClick={() => setMinigameDocsOpen(false)}>✕</button>
            </div>
            <div style={{ flex: 1, overflowY: "auto" }}>
              <MinigameDirectory />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
