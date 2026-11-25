import { CheckCircle2, Cpu, Database, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import type { HealthResponse } from "../types/api";

interface SettingsPageProps {
  health: HealthResponse | null;
  onRefreshHealth: () => Promise<void>;
}

export function SettingsPage({ health, onRefreshHealth }: SettingsPageProps) {
  const llm = health?.llm;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">Provider Settings</h2>
            <p className="text-sm text-slate-400">
              Active LLM provider configuration managed safely on the backend.
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

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 text-xs leading-relaxed text-slate-300">
          <div className="mb-2 flex items-center gap-2 font-semibold text-white">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            How Provider Switching Works
          </div>
          <p className="text-slate-400">
            API keys are stored only on the server in <code className="text-slate-200">backend/.env</code>{" "}
            and are never exposed to the browser. To switch providers without changing code, update{" "}
            <code className="text-slate-200">LLM_PROVIDER=groq</code> or{" "}
            <code className="text-slate-200">LLM_PROVIDER=openrouter</code> in{" "}
            <code className="text-slate-200">backend/.env</code> and restart the FastAPI server.
          </p>
        </div>
      </div>
    </div>
  );
}
