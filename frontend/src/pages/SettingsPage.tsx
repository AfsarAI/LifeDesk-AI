import { FormEvent, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  RefreshCw,
  ShieldCheck,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { apiClient, ApiError, setStoredSessionToken } from "../services/apiClient";
import type { HealthResponse, UserProfile } from "../types/api";

interface SettingsPageProps {
  health: HealthResponse | null;
  currentUser: UserProfile | null;
  users: UserProfile[];
  onRefreshHealth: () => Promise<void>;
  onUserChanged: () => Promise<void>;
}

const COMMON_TIMEZONES = [
  "UTC",
  "Asia/Kolkata",
  "America/New_York",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Tokyo",
];

export function SettingsPage({
  health,
  currentUser,
  users,
  onRefreshHealth,
  onUserChanged,
}: SettingsPageProps) {
  const llm = health?.llm;
  const [timezone, setTimezone] = useState(currentUser?.timezone || "UTC");
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSaveTimezone(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setStatusMsg(null);
    try {
      await apiClient.updateTimezone(timezone);
      await onUserChanged();
      setStatusMsg(`Updated timezone to ${timezone}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update timezone.");
    }
  }

  async function handleSwitchUser(userId: number) {
    setError(null);
    setStatusMsg(null);
    try {
      const res = await apiClient.loginUser({ user_id: userId });
      setStoredSessionToken(res.access_token);
      setTimezone(res.user.timezone);
      await onUserChanged();
      setStatusMsg(`Switched LifeDesk session to ${res.user.name || res.user.email}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to switch user.");
    }
  }

  async function handleRegisterUser(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim() || !newEmail.trim()) return;
    setError(null);
    setStatusMsg(null);
    try {
      const res = await apiClient.registerUser({
        name: newName.trim(),
        email: newEmail.trim(),
        timezone,
      });
      setStoredSessionToken(res.access_token);
      setNewName("");
      setNewEmail("");
      await onUserChanged();
      setStatusMsg(`Created and signed into ${res.user.email}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create user.");
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">Settings & Session</h2>
            <p className="text-sm text-slate-400">
              LLM provider status, timezone preferences, and LifeDesk user profile isolation.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void onRefreshHealth()}
            className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200 hover:bg-slate-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh Status
          </button>
        </div>

        {statusMsg && (
          <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/40 px-4 py-2.5 text-xs text-emerald-200">
            {statusMsg}
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-2.5 text-xs text-rose-200">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <Cpu className="h-4 w-4 text-indigo-400" />
              LLM Provider
            </div>
            <p className="mt-2 text-lg font-semibold uppercase text-white">
              {llm?.provider ?? "Unavailable"}
            </p>
            <p className="mt-1 font-mono text-xs text-indigo-300">{llm?.model || "—"}</p>
            <p className="mt-2 truncate text-xs text-slate-500">{llm?.base_url || "—"}</p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <Database className="h-4 w-4 text-indigo-400" />
              Backend & Key Status
            </div>
            <div className="mt-2 flex items-center gap-2 text-sm font-medium text-white">
              {llm?.configured ? (
                <>
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  Provider Key Configured
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4 text-amber-400" />
                  Missing Provider Key
                </>
              )}
            </div>
            <p className="mt-1.5 text-xs text-slate-400">
              {llm?.status_message ?? "Could not reach backend /api/health."}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              SQLite Database:{" "}
              <span className="font-medium text-slate-300">{health?.database ?? "unknown"}</span>
            </p>
          </div>
        </div>

        <form
          onSubmit={(e) => void handleSaveTimezone(e)}
          className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5"
        >
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <Clock className="h-4 w-4 text-indigo-400" />
            Calendar Timezone
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
            >
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500"
            >
              Save Timezone
            </button>
          </div>
        </form>

        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <Users className="h-4 w-4 text-indigo-400" />
            LifeDesk Application User (Separate from Google OAuth)
          </div>
          <div className="flex flex-wrap gap-2">
            {users.map((u) => {
              const active = currentUser?.id === u.id;
              return (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => void handleSwitchUser(u.id)}
                  className={`rounded-xl border px-3 py-2 text-xs transition ${
                    active
                      ? "border-indigo-500 bg-indigo-500/20 font-medium text-indigo-200"
                      : "border-slate-800 bg-slate-950 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  {u.name || u.email} (#{u.id})
                </button>
              );
            })}
          </div>

          <form onSubmit={(e) => void handleRegisterUser(e)} className="grid gap-2.5 sm:grid-cols-3">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New user name"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white"
            />
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="New user email"
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white"
            />
            <button
              type="submit"
              disabled={!newName.trim() || !newEmail.trim()}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-45"
            >
              <UserPlus className="h-3.5 w-3.5" />
              Create & Switch User
            </button>
          </form>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 text-xs leading-relaxed text-slate-300">
          <div className="mb-2 flex items-center gap-2 font-semibold text-white">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            Security Note
          </div>
          <p className="text-slate-400">
            LLM API keys and Google OAuth tokens are stored exclusively on the backend and are never
            exposed to React. Switching LifeDesk users isolates tasks, memories, conversations,
            approvals, and Google OAuth connections per user.
          </p>
        </div>
      </div>
    </div>
  );
}
