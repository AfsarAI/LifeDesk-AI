import { FormEvent, useState } from "react";
import {
  CheckCircle2,
  Circle,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { apiClient, ApiError } from "../services/apiClient";
import type { Task } from "../types/api";

interface TasksPageProps {
  tasks: Task[];
  counts: { total: number; pending: number; completed: number };
  onRefresh: (params?: { status?: string; q?: string }) => Promise<void>;
}

export function TasksPage({ tasks, counts, onRefresh }: TasksPageProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "completed">("all");
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [description, setDescription] = useState("");
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDueDate, setEditDueDate] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function applyFilter(nextStatus = statusFilter, nextQuery = searchQuery) {
    try {
      await onRefresh({
        status: nextStatus === "all" ? undefined : nextStatus,
        q: nextQuery.trim() || undefined,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load tasks.");
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || busy) return;
    setBusy(true);
    try {
      await apiClient.createTask({
        title: title.trim(),
        due_date: dueDate.trim() || null,
        description: description.trim() || null,
      });
      setTitle("");
      setDueDate("");
      setDescription("");
      await applyFilter();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create task.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleStatus(task: Task) {
    setBusy(true);
    try {
      await apiClient.updateTask(task.id, {
        status: task.status === "completed" ? "pending" : "completed",
      });
      await applyFilter();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update task.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(taskId: number) {
    setBusy(true);
    try {
      await apiClient.deleteTask(taskId);
      await applyFilter();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete task.");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(task: Task) {
    setEditingTask(task);
    setEditTitle(task.title);
    setEditDueDate(task.due_date ?? "");
    setEditDescription(task.description ?? "");
  }

  async function handleSaveEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingTask || !editTitle.trim()) return;
    setBusy(true);
    try {
      await apiClient.updateTask(editingTask.id, {
        title: editTitle.trim(),
        due_date: editDueDate.trim() || null,
        description: editDescription.trim() || null,
      });
      setEditingTask(null);
      await applyFilter();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-white">Tasks Dashboard</h2>
          <p className="text-sm text-slate-400">
            Create, search, update, and complete tasks stored in SQLite.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
            <p className="text-xs text-slate-400">Total Tasks</p>
            <p className="mt-1 text-2xl font-semibold text-white">{counts.total}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
            <p className="text-xs text-slate-400">Pending</p>
            <p className="mt-1 text-2xl font-semibold text-amber-400">{counts.pending}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
            <p className="text-xs text-slate-400">Completed</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-400">{counts.completed}</p>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-2.5 text-xs text-rose-200">
            {error}
          </div>
        )}

        <form
          onSubmit={(e) => void handleCreate(e)}
          className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4"
        >
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Create New Task
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Task title (required)"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              required
            />
            <input
              type="text"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              placeholder="Due date (optional, e.g. 2026-11-30)"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={busy || !title.trim()}
              className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              Add Task
            </button>
          </div>
        </form>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
            <Search className="h-4 w-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                const val = e.target.value;
                setSearchQuery(val);
                void applyFilter(statusFilter, val);
              }}
              placeholder="Search tasks by title or description..."
              className="w-full bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
            />
          </div>
          <div className="flex gap-1.5 rounded-xl border border-slate-800 bg-slate-900 p-1">
            {(["all", "pending", "completed"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => {
                  setStatusFilter(tab);
                  void applyFilter(tab, searchQuery);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition ${
                  statusFilter === tab
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2.5">
          {tasks.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-10 text-center text-sm text-slate-500">
              No matching tasks found.
            </div>
          ) : (
            tasks.map((task) => {
              const isCompleted = task.status === "completed";
              return (
                <div
                  key={task.id}
                  className="flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex items-start gap-3">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleToggleStatus(task)}
                      className="mt-0.5 text-slate-400 hover:text-emerald-400"
                      title={isCompleted ? "Mark as pending" : "Mark as completed"}
                    >
                      {isCompleted ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                      ) : (
                        <Circle className="h-5 w-5" />
                      )}
                    </button>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-slate-500">#{task.id}</span>
                        <h3
                          className={`text-sm font-medium ${
                            isCompleted ? "text-slate-400 line-through" : "text-white"
                          }`}
                        >
                          {task.title}
                        </h3>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            isCompleted
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-amber-500/15 text-amber-300"
                          }`}
                        >
                          {task.status}
                        </span>
                      </div>
                      {task.description && (
                        <p className="mt-1 text-xs text-slate-400">{task.description}</p>
                      )}
                      {task.due_date && (
                        <p className="mt-1 text-xs text-indigo-300">Due: {task.due_date}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 self-end sm:self-center">
                    <button
                      type="button"
                      onClick={() => startEdit(task)}
                      className="rounded-lg border border-slate-800 p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
                      title="Edit task"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleDelete(task.id)}
                      className="rounded-lg border border-slate-800 p-2 text-slate-400 hover:border-rose-500/40 hover:bg-rose-950/40 hover:text-rose-300"
                      title="Delete task"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {editingTask && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <form
              onSubmit={(e) => void handleSaveEdit(e)}
              className="w-full max-w-md space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-5"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">Edit Task #{editingTask.id}</h3>
                <button
                  type="button"
                  onClick={() => setEditingTask(null)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
                required
              />
              <input
                type="text"
                value={editDueDate}
                onChange={(e) => setEditDueDate(e.target.value)}
                placeholder="Due date"
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
              />
              <textarea
                rows={3}
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Description"
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingTask(null)}
                  className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-xl bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
