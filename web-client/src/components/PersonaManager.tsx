import { useEffect, useState } from "react";
import type { Persona, CreatePersonaRequest, UpdatePersonaRequest } from "../types";
import {
  listPersonas,
  createPersona,
  updatePersona,
  deletePersona,
} from "../api/client";

interface PersonaModalProps {
  open: boolean;
  persona?: Persona | null;
  onClose: () => void;
  onSaved: (p: Persona) => void;
}

function PersonaModal({ open, persona, onClose, onSaved }: PersonaModalProps) {
  const pronounPresets = {
    he: { sub: "he", obj: "him", poss: "his", poss_obj: "his" },
    she: { sub: "she", obj: "her", poss: "her", poss_obj: "hers" },
    they: { sub: "they", obj: "them", poss: "their", poss_obj: "theirs" },
  } as const;

  const [pronounPreset, setPronounPreset] = useState<"he" | "she" | "they" | "custom">("they");
  const [name, setName] = useState("");
  const [pronounSub, setPronounSub] = useState("");
  const [pronounObj, setPronounObj] = useState("");
  const [pronounPoss, setPronounPoss] = useState("");
  const [pronounPossObj, setPronounPossObj] = useState("");
  const [appearance, setAppearance] = useState("");
  const [background, setBackground] = useState("");
  const [personality, setPersonality] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const applyPronounPreset = (preset: "he" | "she" | "they" | "custom") => {
    setPronounPreset(preset);
    if (preset === "custom") {
      return;
    }

    const values = pronounPresets[preset];
    setPronounSub(values.sub);
    setPronounObj(values.obj);
    setPronounPoss(values.poss);
    setPronounPossObj(values.poss_obj);
  };

  const derivePronounPreset = (sub: string, obj: string, poss: string, possObj: string) => {
    if (
      sub === pronounPresets.he.sub &&
      obj === pronounPresets.he.obj &&
      poss === pronounPresets.he.poss &&
      possObj === pronounPresets.he.poss_obj
    ) {
      return "he" as const;
    }
    if (
      sub === pronounPresets.she.sub &&
      obj === pronounPresets.she.obj &&
      poss === pronounPresets.she.poss &&
      possObj === pronounPresets.she.poss_obj
    ) {
      return "she" as const;
    }
    if (
      sub === pronounPresets.they.sub &&
      obj === pronounPresets.they.obj &&
      poss === pronounPresets.they.poss &&
      possObj === pronounPresets.they.poss_obj
    ) {
      return "they" as const;
    }
    return "custom" as const;
  };

  useEffect(() => {
    if (open) {
      if (persona) {
        setName(persona.name);
        setPronounSub(persona.pronoun_sub);
        setPronounObj(persona.pronoun_obj);
        setPronounPoss(persona.pronoun_poss);
        setPronounPossObj(persona.pronoun_poss_obj);
        setPronounPreset(
          derivePronounPreset(
            persona.pronoun_sub,
            persona.pronoun_obj,
            persona.pronoun_poss,
            persona.pronoun_poss_obj,
          ),
        );
        setAppearance(persona.appearance);
        setBackground(persona.background);
        setPersonality(persona.personality);
      } else {
        setName("");
        applyPronounPreset("they");
        setAppearance("");
        setBackground("");
        setPersonality("");
      }
      setError(null);
    }
  }, [open, persona]);

  if (!open) return null;

  const handleSubmit = async () => {
    setError(null);
    if (!name.trim() || !pronounSub.trim() || !pronounObj.trim() || !pronounPoss.trim() || !pronounPossObj.trim()) {
      setError("Name and all pronouns are required.");
      return;
    }
    setLoading(true);
    try {
      if (persona) {
        const body: UpdatePersonaRequest = {
          name: name.trim(),
          pronoun_sub: pronounSub.trim(),
          pronoun_obj: pronounObj.trim(),
          pronoun_poss: pronounPoss.trim(),
          pronoun_poss_obj: pronounPossObj.trim(),
          appearance: appearance.trim(),
          background: background.trim(),
          personality: personality.trim(),
        };
        const updated = await updatePersona(persona.id, body);
        onSaved(updated);
      } else {
        const body: CreatePersonaRequest = {
          name: name.trim(),
          pronoun_sub: pronounSub.trim(),
          pronoun_obj: pronounObj.trim(),
          pronoun_poss: pronounPoss.trim(),
          pronoun_poss_obj: pronounPossObj.trim(),
          appearance: appearance.trim(),
          background: background.trim(),
          personality: personality.trim(),
        };
        const created = await createPersona(body);
        onSaved(created);
      }
      onClose();
    } catch (e: any) {
      setError(e.message || "Failed to save persona.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>{persona ? "Edit Persona" : "Create Persona"}</h2>

        {error && <div className="error-banner"><span>{error}</span></div>}

        <label className="modal-label">
          Name *
          <input type="text" className="modal-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Robin" />
        </label>

        <label className="modal-label">
          Pronoun preset
          <select
            className="modal-input"
            value={pronounPreset}
            onChange={(e) => applyPronounPreset(e.target.value as "he" | "she" | "they" | "custom")}
          >
            <option value="he">he/him/his/his</option>
            <option value="she">she/her/her/hers</option>
            <option value="they">they/them/their/theirs</option>
            <option value="custom">custom</option>
          </select>
        </label>

        {pronounPreset === "custom" && (
          <>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <label className="modal-label" style={{ flex: 1 }}>
                Pronoun (Sub) *
                <input type="text" className="modal-input" value={pronounSub} onChange={(e) => {
                  setPronounSub(e.target.value);
                  setPronounPreset("custom");
                }} placeholder="they" />
              </label>
              <label className="modal-label" style={{ flex: 1 }}>
                Pronoun (Obj) *
                <input type="text" className="modal-input" value={pronounObj} onChange={(e) => {
                  setPronounObj(e.target.value);
                  setPronounPreset("custom");
                }} placeholder="them" />
              </label>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <label className="modal-label" style={{ flex: 1 }}>
                Pronoun (Poss) *
                <input type="text" className="modal-input" value={pronounPoss} onChange={(e) => {
                  setPronounPoss(e.target.value);
                  setPronounPreset("custom");
                }} placeholder="their" />
              </label>
              <label className="modal-label" style={{ flex: 1 }}>
                Pronoun (Poss Obj) *
                <input type="text" className="modal-input" value={pronounPossObj} onChange={(e) => {
                  setPronounPossObj(e.target.value);
                  setPronounPreset("custom");
                }} placeholder="theirs" />
              </label>
            </div>
          </>
        )}

        <label className="modal-label">
          Appearance
          <textarea className="modal-input" value={appearance} onChange={(e) => setAppearance(e.target.value)} placeholder="Physical description..." />
        </label>
        
        <label className="modal-label">
          Background
          <textarea className="modal-input" value={background} onChange={(e) => setBackground(e.target.value)} placeholder="Backstory..." />
        </label>

        <label className="modal-label">
          Personality
          <textarea className="modal-input" value={personality} onChange={(e) => setPersonality(e.target.value)} placeholder="Traits and demeanor..." />
        </label>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? "Saving..." : "Save Persona"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PersonaManager() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null);

  const fetchPersonas = async () => {
    try {
      setLoading(true);
      const data = await listPersonas();
      setPersonas(data);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to load personas.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPersonas();
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this persona?")) return;
    try {
      await deletePersona(id);
      setPersonas((prev) => prev.filter((p) => p.id !== id));
    } catch (e: any) {
      alert("Failed to delete persona: " + e.message);
    }
  };

  const handleSaved = (p: Persona) => {
    if (editingPersona) {
      setPersonas((prev) => prev.map((item) => (item.id === p.id ? p : item)));
    } else {
      setPersonas((prev) => [...prev, p]);
    }
  };

  const openCreateModal = () => {
    setEditingPersona(null);
    setModalOpen(true);
  };

  const openEditModal = (p: Persona) => {
    setEditingPersona(p);
    setModalOpen(true);
  };

  return (
    <div className="cartridge-library">
      <div className="library-header">
        <h2>🎭 My Personas</h2>
        <div style={{ display: "flex", gap: "1rem" }}>
          <button className="btn btn-primary" onClick={openCreateModal}>
            + New Persona
          </button>
          <button className="btn btn-secondary" onClick={fetchPersonas} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button className="btn btn-small" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {loading && personas.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
          Loading personas...
        </div>
      ) : personas.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", border: "1px dashed var(--border-color)", borderRadius: "8px", marginTop: "1rem" }}>
          No personas found. Create one to get started!
        </div>
      ) : (
        <div className="library-grid" style={{ marginTop: "1rem" }}>
          {personas.map((p) => (
            <div key={p.id} className="cartridge-card">
              <div className="cartridge-header">
                <h3>{p.name}</h3>
                <span className="cartridge-badge">
                  {p.pronoun_sub}/{p.pronoun_obj}
                </span>
              </div>
              <p className="cartridge-desc" style={{ WebkitLineClamp: 2 }}>
                {p.appearance || "No appearance description."}
              </p>
              
              <div className="cartridge-actions" style={{ marginTop: "auto", paddingTop: "1rem", borderTop: "1px solid var(--border-color)", display: "flex", justifyContent: "space-between" }}>
                <button className="btn btn-small btn-secondary" onClick={() => openEditModal(p)}>
                  Edit
                </button>
                <button className="btn btn-small btn-secondary" style={{ color: "var(--color-error)" }} onClick={() => handleDelete(p.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <PersonaModal
        open={modalOpen}
        persona={editingPersona}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />
    </div>
  );
}
