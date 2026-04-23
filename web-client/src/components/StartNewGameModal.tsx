import { useEffect, useState } from "react";
import type { Cartridge, CartridgeVersion, Persona } from "../types";
import {
  listCartridges,
  listCartridgeVersions,
  listPersonas,
  createGameInstance,
  setInstanceId,
} from "../api/client";

interface StartNewGameModalProps {
  open: boolean;
  onClose: () => void;
  onStart: (turnId: string | undefined) => void;
}

export default function StartNewGameModal({ open, onClose, onStart }: StartNewGameModalProps) {
  const [cartridges, setCartridges] = useState<Cartridge[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);
  
  const [selectedCartridgeId, setSelectedCartridgeId] = useState<string>("");
  const [versions, setVersions] = useState<CartridgeVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");
  
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>("");
  
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadData();
    }
  }, [open]);

  const loadData = async () => {
    setLoadingInitial(true);
    setError(null);
    try {
      const [cData, pData] = await Promise.all([listCartridges(), listPersonas()]);
      setCartridges(cData);
      setPersonas(pData);
      
      if (cData.length > 0) {
        setSelectedCartridgeId(cData[0].id);
      }
      if (pData.length > 0) {
        setSelectedPersonaId(pData[0].id);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load data.");
    } finally {
      setLoadingInitial(false);
    }
  };

  useEffect(() => {
    if (selectedCartridgeId) {
      fetchVersions(selectedCartridgeId);
    } else {
      setVersions([]);
      setSelectedVersionId("");
    }
  }, [selectedCartridgeId]);

  const fetchVersions = async (cid: string) => {
    setLoadingVersions(true);
    try {
      const vData = await listCartridgeVersions(cid);
      setVersions(vData);
      if (vData.length > 0) {
        setSelectedVersionId(vData[vData.length - 1].id); // default to newest (assuming last)
      } else {
        setSelectedVersionId("");
      }
    } catch (e: any) {
      console.error(e);
      setVersions([]);
      setSelectedVersionId("");
    } finally {
      setLoadingVersions(false);
    }
  };

  if (!open) return null;

  const handleStart = async () => {
    setError(null);
    if (!selectedVersionId) {
      setError("Please select a cartridge version.");
      return;
    }
    if (!selectedPersonaId) {
      setError("Please select a persona. You may need to create one first.");
      return;
    }
    
    setStarting(true);
    try {
      const resp = await createGameInstance({
        version_id: selectedVersionId,
        persona_id: selectedPersonaId,
      });
      setInstanceId(resp.instance_id);
      onStart(resp.turn_id);
      onClose();
    } catch (e: any) {
      setError(e.message || "Failed to start game.");
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>🚀 Start New Game</h2>

        {error && <div className="error-banner"><span>{error}</span></div>}

        {loadingInitial ? (
          <p>Loading...</p>
        ) : (
          <>
            <label className="modal-label">
              Select Cartridge
              <select 
                className="modal-input" 
                value={selectedCartridgeId} 
                onChange={(e) => setSelectedCartridgeId(e.target.value)}
              >
                {cartridges.length === 0 && <option value="">No Cartridges Available</option>}
                {cartridges.map(c => (
                  <option key={c.id} value={c.id}>{c.title}</option>
                ))}
              </select>
            </label>

            <label className="modal-label">
              Select Version
              <select 
                className="modal-input" 
                value={selectedVersionId} 
                onChange={(e) => setSelectedVersionId(e.target.value)}
                disabled={loadingVersions || versions.length === 0}
              >
                {loadingVersions && <option value="">Loading versions...</option>}
                {!loadingVersions && versions.length === 0 && <option value="">No Versions Available</option>}
                {!loadingVersions && versions.map(v => (
                  <option key={v.id} value={v.id}>{v.version_tag}</option>
                ))}
              </select>
            </label>

            <label className="modal-label">
              Select Persona
              <select 
                className="modal-input" 
                value={selectedPersonaId} 
                onChange={(e) => setSelectedPersonaId(e.target.value)}
              >
                {personas.length === 0 && <option value="">No Personas Available (Create one in Library!)</option>}
                {personas.map(p => (
                  <option key={p.id} value={p.id}>{p.name} ({p.pronoun_sub}/{p.pronoun_obj})</option>
                ))}
              </select>
            </label>

            <div className="modal-actions" style={{ marginTop: "2rem" }}>
              <button className="btn btn-secondary" onClick={onClose} disabled={starting}>
                Cancel
              </button>
              <button 
                className="btn btn-primary" 
                onClick={handleStart} 
                disabled={starting || !selectedVersionId || !selectedPersonaId}
              >
                {starting ? "Starting..." : "Start Game"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
