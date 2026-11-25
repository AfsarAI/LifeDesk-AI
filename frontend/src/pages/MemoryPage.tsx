import { FormEvent, useState } from "react";
import { Brain, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { apiClient, ApiError } from "../services/apiClient";
import type { Memory } from "../types/api";

interface MemoryPageProps {
  memories: Memory[];
  onRefresh: () => Promise<void>;
}

export function MemoryPage({ memories, onRefresh }: MemoryPageProps) {
  const [keyInput, setKeyInput] = useState("");
  const [valueInput, setValueInput] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editKey, setEditKey] = useState("");
  const [editValue, setEditValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!keyInput.trim() || !valueInput.trim() || busy) return;
    setBusy(true);
    try {
      await apiClient.createOrUpdateMemory({
        key: keyInput.trim(),
        value: valueInput.trim(),
      });
      setKeyInput("");
      setValueInput("");
      setError(null);
      await onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save memory.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveEdit(memoryId: number) {
    if (!editKey.trim() || !editValue.trim() || busy) return;
    setBusy(true);
    try {
      await apiClient.updateMemory(memoryId, {
        key: editKey.trim(),
        value: editValue.trim(),
      });
      setEditingId(null);
      setError(null);
      await onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update memory.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(memoryId: number) {
    setBusy(true);
    try {
      await apiClient.deleteMemory(memoryId);
      setError(null);
      await onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete memory.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
            <Brain className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">Persistent Memory</h2>
            <p className="text-sm text-slate-400">
              Long-term key-value preferences saved in SQLite across restarts.
            </p>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-2.5 text-xs text-rose-200">
            {error}
          </div>
        )}

        <form
          onSubmit={(e) => void handleAdd(e)}
          className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4"
        >
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Add or Update Memory
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              type="text"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="Key (e.g. meeting_preference)"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              required
            />
            <input
              type="text"
              value={valueInput}
              onChange={(e) => setValueInput(e.target.value)}
              placeholder="Value (e.g. afternoon)"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              required
            />
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={busy || !keyInput.trim() || !valueInput.trim()}
              className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              Save Memory
            </button>
          </div>
        </form>

        <div className="space-y-2.5">
          {memories.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-10 text-center text-sm text-slate-500">
              No long-term memories saved yet. Tell the assistant your preferences in Chat or add
              one above.
            </div>
          ) : (
            memories.map((memory) => {
              const isEditing = editingId === memory.id;
              return (
                <div
                  key={memory.id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4"
                >
                  {isEditing ? (
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                      <input
                        type="text"
                        value={editKey}
                        onChange={(e) => setEditKey(e.target.value)}
                        className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-xs text-indigo-300"
                      />
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-white"
                      />
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleSaveEdit(memory.id)}
                          className="rounded-lg bg-emerald-600 p-2 text-white hover:bg-emerald-500"
                          title="Save"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="rounded-lg border border-slate-700 p-2 text-slate-300"
                          title="Cancel"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="font-mono text-xs font-medium text-indigo-300">
                          {memory.key}
                        </p>
                        <p className="mt-1 text-sm text-slate-100">{memory.value}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(memory.id);
                            setEditKey(memory.key);
                            setEditValue(memory.value);
                          }}
                          className="rounded-lg border border-slate-800 p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                          title="Edit memory"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleDelete(memory.id)}
                          className="rounded-lg border border-slate-800 p-2 text-slate-400 hover:border-rose-500/40 hover:bg-rose-950/40 hover:text-rose-300"
                          title="Delete memory"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
