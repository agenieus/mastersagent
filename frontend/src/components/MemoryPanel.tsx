import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Memory, MemoryStats } from "@/lib/types";
import styles from "../app/chat/chat.module.css";

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function MemoryPanel({ isOpen, onClose }: MemoryPanelProps) {
  const [activeMemories, setActiveMemories] = useState<Memory[]>([]);
  const [archivedMemories, setArchivedMemories] = useState<Memory[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [viewArchived, setViewArchived] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const active = await api.memory.listActive();
      setActiveMemories(active.sort((a, b) => b.decay_score - a.decay_score));
      
      const archived = await api.memory.listArchived();
      setArchivedMemories(archived.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
      
      const s = await api.memory.getStats();
      setStats(s);
    } catch (err) {
      console.error("Failed to fetch memories", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchMemories();
    }
  }, [isOpen]);

  const handleRunDecay = async () => {
    try {
      setLoading(true);
      await api.memory.runDecay();
      await fetchMemories();
    } catch (err) {
      console.error("Failed to run decay", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.memory.delete(id);
      await fetchMemories();
    } catch (err) {
      console.error("Failed to delete memory", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "400px",
        height: "100vh",
        backgroundColor: "var(--bg-secondary)",
        borderLeft: "1px solid var(--border-color)",
        padding: "1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        zIndex: 50,
        boxShadow: "-4px 0 15px rgba(0,0,0,0.1)",
        overflowY: "auto",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: "1.25rem", margin: 0 }}>Memory System</h2>
        <button onClick={onClose} style={{ cursor: "pointer", background: "none", border: "none", fontSize: "1.5rem", color: "var(--text-primary)" }}>×</button>
      </div>

      {stats && (
        <div style={{ backgroundColor: "var(--bg-primary)", padding: "1rem", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span>Active: {stats.active_count}</span>
            <span>Archived: {stats.archived_count}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.875rem", color: "var(--text-muted)" }}>
            <span>Avg Decay: {stats.average_decay_score.toFixed(2)}</span>
            <span>Avg Importance: {stats.average_importance.toFixed(2)}</span>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button
          onClick={() => setViewArchived(false)}
          style={{ flex: 1, padding: "0.5rem", borderRadius: "4px", backgroundColor: !viewArchived ? "var(--accent-color)" : "transparent", color: !viewArchived ? "white" : "var(--text-primary)", border: "1px solid var(--border-color)", cursor: "pointer" }}
        >
          Active
        </button>
        <button
          onClick={() => setViewArchived(true)}
          style={{ flex: 1, padding: "0.5rem", borderRadius: "4px", backgroundColor: viewArchived ? "var(--accent-color)" : "transparent", color: viewArchived ? "white" : "var(--text-primary)", border: "1px solid var(--border-color)", cursor: "pointer" }}
        >
          Archived / Superseded
        </button>
      </div>

      <button
        onClick={handleRunDecay}
        disabled={loading}
        style={{ width: "100%", padding: "0.75rem", backgroundColor: "var(--accent-color)", color: "white", borderRadius: "8px", border: "none", cursor: loading ? "not-allowed" : "pointer", fontWeight: "bold" }}
      >
        {loading ? "Processing..." : "Run Decay Engine"}
      </button>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
        {(viewArchived ? archivedMemories : activeMemories).map(mem => (
          <div key={mem.memory_id} style={{ backgroundColor: "var(--bg-primary)", padding: "1rem", borderRadius: "8px", border: "1px solid var(--border-color)", position: "relative" }}>
            <button onClick={() => handleDelete(mem.memory_id)} style={{ position: "absolute", top: "0.5rem", right: "0.5rem", background: "none", border: "none", color: "red", cursor: "pointer", padding: "4px" }}>
              ✕
            </button>
            <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", paddingRight: "1.5rem" }}>{mem.fact_text}</p>
            
            <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.75rem", flexWrap: "wrap" }}>
              <span style={{ backgroundColor: "rgba(255,255,255,0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                Imp: {mem.importance_weight}
              </span>
              <span style={{ backgroundColor: "rgba(255,255,255,0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                Score: {mem.decay_score.toFixed(2)}
              </span>
              <span style={{ backgroundColor: "rgba(255,255,255,0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                Used: {mem.retrieval_count}
              </span>
            </div>
            
            {!mem.validity_flag && mem.superseded_by && (
              <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#ff8888" }}>
                Superseded
              </div>
            )}
          </div>
        ))}
        {(viewArchived ? archivedMemories : activeMemories).length === 0 && (
          <p style={{ textAlign: "center", color: "var(--text-muted)", marginTop: "2rem" }}>No memories found.</p>
        )}
      </div>
    </div>
  );
}
