/**
 * CartridgeLibrary — Cartridge management view (MNS-Cartridge).
 *
 * Provides:
 *   - A list of all available cartridges.
 *   - A "Create Cartridge" modal to define parent metadata.
 *   - An "Upload Version" modal to push validated version files.
 *   - Inline display of validation errors from the engine's CartridgeLoader.
 */

import { useEffect, useRef, useState } from "react";
import yaml from "js-yaml";
import type { Cartridge, CartridgeVersion, CreateCartridgeRequest } from "../types";
import {
  createCartridge,
  deleteCartridge,
  listCartridges,
  listCartridgeVersions,
  uploadCartridgeVersion,
} from "../api/client";
import CartridgeBuilder, { type BuilderPanes } from "./CartridgeBuilder";

async function fetchWithRetry<T>(task: () => Promise<T>, attempts = 3, delayMs = 250): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await task();
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }

  throw lastError instanceof Error ? lastError : new Error("Request failed.");
}

// ---------------------------------------------------------------------------
// CreateCartridgeModal
// ---------------------------------------------------------------------------

interface CreateCartridgeModalProps {
  open: boolean;
  cartridge?: Cartridge | null;
  onClose: () => void;
  onSaved: (c: Cartridge) => void;
}

function CreateCartridgeModal({ open, cartridge, onClose, onSaved }: CreateCartridgeModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [genre, setGenre] = useState("");
  const [visibility, setVisibility] = useState<"PUBLIC" | "PRIVATE">("PUBLIC");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      if (cartridge) {
        setTitle(cartridge.title);
        setDescription(cartridge.description);
        setGenre(cartridge.genre);
        setVisibility(cartridge.visibility);
      } else {
        setTitle("");
        setDescription("");
        setGenre("");
        setVisibility("PUBLIC");
      }
      setError(null);
    }
  }, [open, cartridge]);

  if (!open) return null;

  const handleSubmit = async () => {
    setError(null);
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    setLoading(true);
    try {
      if (cartridge) {
        const { updateCartridge } = await import("../api/client");
        const updated = await updateCartridge(cartridge.id, {
          title: title.trim(),
          description: description.trim(),
          genre: genre.trim(),
          visibility,
        });
        onSaved(updated);
      } else {
        const body: CreateCartridgeRequest = {
          title: title.trim(),
          description: description.trim(),
          genre: genre.trim(),
          visibility,
        };
        const created = await createCartridge(body);
        onSaved(created);
      }
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save cartridge.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>{cartridge ? "✏️ Edit Cartridge" : "📦 Create Cartridge"}</h2>

        {error && <div className="error-banner"><span>{error}</span></div>}

        <label className="modal-label">
          Title *
          <input
            type="text"
            className="modal-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="My Adventure"
          />
        </label>

        <label className="modal-label">
          Description
          <input
            type="text"
            className="modal-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="A short description"
          />
        </label>

        <label className="modal-label">
          Genre
          <input
            type="text"
            className="modal-input"
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            placeholder="e.g. dark-fantasy"
          />
        </label>

        <label className="modal-label">
          Visibility
          <select
            className="modal-input"
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as "PUBLIC" | "PRIVATE")}
          >
            <option value="PUBLIC">Public</option>
            <option value="PRIVATE">Private</option>
          </select>
        </label>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// UploadVersionModal
// ---------------------------------------------------------------------------

interface UploadVersionModalProps {
  open: boolean;
  cartridgeId: string;
  onClose: () => void;
  onUploaded: (v: CartridgeVersion) => void;
}

function UploadVersionModal({ open, cartridgeId, onClose, onUploaded }: UploadVersionModalProps) {
  const [versionTag, setVersionTag] = useState("");
  const [uploadMode, setUploadMode] = useState<"zip" | "files">("zip");
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [yareFile, setYareFile] = useState<File | null>(null);
  const [loreFile, setLoreFile] = useState<File | null>(null);
  const [directivesFile, setDirectivesFile] = useState<File | null>(null);
  const [firstMessageFile, setFirstMessageFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const zipRef = useRef<HTMLInputElement>(null);
  const yareRef = useRef<HTMLInputElement>(null);
  const loreRef = useRef<HTMLInputElement>(null);
  const dirRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const handleUpload = async () => {
    setError(null);
    if (!versionTag.trim()) {
      setError("Version tag is required (e.g. 1.0.0).");
      return;
    }
    if (uploadMode === "zip" && !zipFile) {
      setError("Please select a ZIP file.");
      return;
    }
    if (uploadMode === "files" && (!yareFile || !loreFile)) {
      setError("Both yare.yaml and bot_lore.md are required.");
      return;
    }

    setLoading(true);
    try {
      const uploaded = await uploadCartridgeVersion(
        cartridgeId,
        versionTag.trim(),
        uploadMode === "zip"
          ? { zipFile: zipFile! }
          : {
              yareFile: yareFile!,
              loreFile: loreFile!,
              directivesFile: directivesFile ?? undefined,
              firstMessageFile: firstMessageFile ?? undefined,
            },
      );
      onUploaded(uploaded);
      onClose();
      setVersionTag("");
      setZipFile(null);
      setYareFile(null);
      setLoreFile(null);
      setDirectivesFile(null);
      setFirstMessageFile(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>⬆️ Upload Version</h2>

        {error && (
          <div className="error-banner">
            <span style={{ whiteSpace: "pre-wrap" }}>{error}</span>
          </div>
        )}

        <label className="modal-label">
          Version Tag *
          <input
            type="text"
            className="modal-input"
            value={versionTag}
            onChange={(e) => setVersionTag(e.target.value)}
            placeholder="1.0.0"
          />
        </label>

        <label className="modal-label">
          Upload Mode
          <select
            className="modal-input"
            value={uploadMode}
            onChange={(e) => setUploadMode(e.target.value as "zip" | "files")}
          >
            <option value="zip">ZIP archive</option>
            <option value="files">Individual files</option>
          </select>
        </label>

        {uploadMode === "zip" ? (
          <label className="modal-label">
            ZIP file (yare.yaml or yare.js + bot_lore.md [+ prompt_directives.yaml])
            <input
              ref={zipRef}
              type="file"
              accept=".zip"
              className="modal-input"
              onChange={(e) => setZipFile(e.target.files?.[0] ?? null)}
            />
          </label>
        ) : (
          <>
            <label className="modal-label">
              yare.yaml or yare.js *
              <input
                ref={yareRef}
                type="file"
                accept=".yaml,.yml,.js"
                className="modal-input"
                onChange={(e) => setYareFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="modal-label">
              bot_lore.md *
              <input
                ref={loreRef}
                type="file"
                accept=".md"
                className="modal-input"
                onChange={(e) => setLoreFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="modal-label">
              prompt_directives.yaml (optional)
              <input
                ref={dirRef}
                type="file"
                accept=".yaml,.yml"
                className="modal-input"
                onChange={(e) => setDirectivesFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="modal-label">
              first-message.md (optional)
              <input
                type="file"
                accept=".md"
                className="modal-input"
                onChange={(e) => setFirstMessageFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </>
        )}

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleUpload} disabled={loading}>
            {loading ? "Uploading…" : "Upload"}
          </button>
        </div>

        <p className="modal-hint">
          Files are validated by the MnesOS CartridgeLoader engine before
          being saved. Validation errors will be shown here.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CartridgeDetail — single cartridge expanded view
// ---------------------------------------------------------------------------

/** Convert a persisted CartridgeVersion to the editor's BuilderPanes shape. */
function versionToPanes(v: CartridgeVersion): BuilderPanes {
  const yareType: "yaml" | "js" = v.yare_type === "js" ? "js" : "yaml";
  const yareRules = yareType === "js" && v.yare_spec_raw
    ? v.yare_spec_raw
    : yaml.dump(v.yare_spec);
  return {
    first_message: v.first_message ?? "",
    prompt_directives: yaml.dump(v.prompt_directives),
    yare_rules: yareRules,
    yare_type: yareType,
    bot_lore: v.bot_lore ?? "",
  };
}

interface CartridgeDetailProps {
  cartridge: Cartridge;
  onDeleted: (id: string) => void;
  onBack: () => void;
  onUpdated?: (c: Cartridge) => void;
}

function CartridgeDetail({ cartridge, onDeleted, onBack, onUpdated }: CartridgeDetailProps) {
  const [versions, setVersions] = useState<CartridgeVersion[]>([]);
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [builderVersion, setBuilderVersion] = useState<CartridgeVersion | null>(null);
  const [newVersionOpen, setNewVersionOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVersions = async () => {
      try {
        const data = await fetchWithRetry(() => listCartridgeVersions(cartridge.id));
        setVersions(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load versions.");
      }
    };
    fetchVersions();
  }, [cartridge.id]);

  // ── Builder drill-down ──────────────────────────────────────────────────
  if (newVersionOpen) {
    return (
      <div>
        <button
          className="btn btn-secondary"
          style={{ marginBottom: "1rem" }}
          onClick={() => setNewVersionOpen(false)}
        >
          ← Back to {cartridge.title}
        </button>
        <CartridgeBuilder cartridgeId={cartridge.id} />
      </div>
    );
  }

  if (builderVersion) {
    return (
      <div>
        <button
          className="btn btn-secondary"
          style={{ marginBottom: "1rem" }}
          onClick={() => setBuilderVersion(null)}
        >
          ← Back to {cartridge.title}
        </button>
        <CartridgeBuilder
          cartridgeId={cartridge.id}
          initialPanes={versionToPanes(builderVersion)}
        />
      </div>
    );
  }

  return (
    <div>
      <button className="btn btn-secondary" style={{ marginBottom: "1rem" }} onClick={onBack}>
        ← Back
      </button>

      <h2 style={{ marginBottom: "0.25rem" }}>
        📦 {cartridge.title}
        <span
          style={{
            fontSize: "0.75rem",
            marginLeft: "0.5rem",
            padding: "2px 6px",
            borderRadius: "4px",
            background: cartridge.visibility === "PUBLIC" ? "#2a6" : "#a62",
            color: "#fff",
          }}
        >
          {cartridge.visibility}
        </span>
      </h2>
      {cartridge.genre && (
        <p style={{ color: "#aaa", marginTop: 0 }}>Genre: {cartridge.genre}</p>
      )}
      {cartridge.description && <p>{cartridge.description}</p>}

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button className="btn btn-small" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button className="btn btn-primary" onClick={() => setEditing(true)}>
          ✏️ Edit Cartridge
        </button>
        <button className="btn btn-primary" onClick={() => setNewVersionOpen(true)}>
          🆕 Create New Version
        </button>
        <button className="btn btn-primary" onClick={() => setUploading(true)}>
          ⬆️ Upload Version
        </button>
        <button
          className="btn btn-danger"
          onClick={async () => {
            try {
              await deleteCartridge(cartridge.id);
              onDeleted(cartridge.id);
            } catch (e: unknown) {
              setError(e instanceof Error ? e.message : "Delete failed.");
            }
          }}
        >
          🗑️ Delete
        </button>
      </div>

      <h3>Versions ({versions.length})</h3>
      {versions.length === 0 ? (
        <p style={{ color: "#aaa" }}>No versions yet. Create one using the builder above or upload files.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #444" }}>
              <th style={{ padding: "0.5rem" }}>Tag</th>
              <th style={{ padding: "0.5rem" }}>Published</th>
              <th style={{ padding: "0.5rem" }}>Checksum</th>
              <th style={{ padding: "0.5rem" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.id} style={{ borderBottom: "1px solid #333" }}>
                <td style={{ padding: "0.5rem" }}>
                  <code>{v.version_tag}</code>
                </td>
                <td style={{ padding: "0.5rem" }}>
                  {v.published_at ? new Date(v.published_at).toLocaleString() : "—"}
                </td>
                <td style={{ padding: "0.5rem" }}>
                  <code style={{ fontSize: "0.7rem" }}>{v.checksum.slice(0, 12)}…</code>
                </td>
                <td style={{ padding: "0.5rem" }}>
                  <button
                    className="btn btn-small btn-secondary"
                    onClick={() => setBuilderVersion(v)}
                    aria-label={`Edit version ${v.version_tag} in builder`}
                  >
                    🔨 Edit in Builder
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <UploadVersionModal
        open={uploading}
        cartridgeId={cartridge.id}
        onClose={() => setUploading(false)}
        onUploaded={(v) => setVersions((prev) => [...prev, v])}
      />
      <CreateCartridgeModal
        open={editing}
        cartridge={cartridge}
        onClose={() => setEditing(false)}
        onSaved={(updated) => {
          if (onUpdated) onUpdated(updated);
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// CartridgeLibrary — top-level view
// ---------------------------------------------------------------------------

export default function CartridgeLibrary() {
  const [cartridges, setCartridges] = useState<Cartridge[]>([]);
  const [selected, setSelected] = useState<Cartridge | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWithRetry(() => listCartridges())
      .then(setCartridges)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load cartridges."),
      )
      .finally(() => setLoading(false));
  }, []);

  if (selected) {
    return (
      <CartridgeDetail
        cartridge={selected}
        onDeleted={(id) => {
          setCartridges((prev) => prev.filter((c) => c.id !== id));
          setSelected(null);
        }}
        onBack={() => setSelected(null)}
        onUpdated={(updated) => {
          setCartridges((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
          setSelected(updated);
        }}
      />
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
        <h2 style={{ margin: 0 }}>📚 Cartridge Library</h2>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>
          + New Cartridge
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button className="btn btn-small" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {loading ? (
        <p style={{ color: "#aaa" }}>Loading…</p>
      ) : cartridges.length === 0 ? (
        <p style={{ color: "#aaa" }}>No cartridges yet. Create one to get started.</p>
      ) : (
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {cartridges.map((c) => (
            <div
              key={c.id}
              style={{
                padding: "0.75rem 1rem",
                border: "1px solid #444",
                borderRadius: "6px",
                cursor: "pointer",
                background: "#1a1a2e",
              }}
              onClick={() => setSelected(c)}
            >
              <strong>{c.title}</strong>
              {c.genre && (
                <span style={{ marginLeft: "0.5rem", color: "#aaa", fontSize: "0.85rem" }}>
                  [{c.genre}]
                </span>
              )}
              <span
                style={{
                  float: "right",
                  fontSize: "0.75rem",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  background: c.visibility === "PUBLIC" ? "#2a6" : "#a62",
                  color: "#fff",
                }}
              >
                {c.visibility}
              </span>
              {c.description && (
                <p style={{ margin: "0.25rem 0 0", color: "#ccc", fontSize: "0.875rem" }}>
                  {c.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <CreateCartridgeModal
        open={creating}
        onClose={() => setCreating(false)}
        onSaved={(c) => {
          setCartridges((prev) => [...prev, c]);
          setSelected(c);
        }}
      />
    </div>
  );
}
