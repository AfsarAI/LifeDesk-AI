import { useState } from "react";
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Mail,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Unplug,
  XCircle,
} from "lucide-react";
import { apiClient, ApiError } from "../services/apiClient";
import type { IntegrationCard } from "../types/api";

interface IntegrationsPageProps {
  integrations: IntegrationCard[];
  oauthConfigured: boolean;
  encryptionConfigured: boolean;
  oauthBanner: { type: "success" | "error"; message: string } | null;
  onDismissBanner: () => void;
  onRefresh: () => Promise<void>;
}

export function IntegrationsPage({
  integrations,
  oauthConfigured,
  encryptionConfigured,
  oauthBanner,
  onDismissBanner,
  onRefresh,
}: IntegrationsPageProps) {
  const [busyProvider, setBusyProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeIntegrations = integrations.filter((i) => i.category === "active");
  const plannedIntegrations = integrations.filter((i) => i.category === "coming_soon");

  async function handleConnect(service: "gmail" | "calendar" | "both") {
    setBusyProvider(service);
    setError(null);
    try {
      const res = await apiClient.connectGoogle(service, "write");
      window.location.assign(res.authorization_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to initiate Google OAuth.");
      setBusyProvider(null);
    }
  }

  async function handleReconnect(service: "gmail" | "calendar" | "both") {
    setBusyProvider(service);
    setError(null);
    try {
      const res = await apiClient.reconnectGoogle(service, "write");
      window.location.assign(res.authorization_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reconnect Google OAuth.");
      setBusyProvider(null);
    }
  }

  async function handleDisconnect(provider: "gmail" | "calendar") {
    setBusyProvider(provider);
    setError(null);
    try {
      await apiClient.disconnectGoogle(provider);
      await onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to disconnect integration.");
    } finally {
      setBusyProvider(null);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-white">Integrations & MCP Connections</h2>
            <p className="text-sm text-slate-400">
              Authorize LifeDesk AI to access your Google services via encrypted OAuth 2.0 tokens.
            </p>
          </div>
          <button
            type="button"
            disabled={busyProvider !== null || !oauthConfigured || !encryptionConfigured}
            onClick={() => void handleConnect("both")}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {busyProvider === "both" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <ExternalLink className="h-3.5 w-3.5" />
            )}
            Connect All Google Services
          </button>
        </div>

        {oauthBanner && (
          <div
            className={`flex items-center justify-between rounded-xl border px-4 py-3 text-xs ${
              oauthBanner.type === "success"
                ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-200"
                : "border-rose-500/40 bg-rose-950/40 text-rose-200"
            }`}
          >
            <span>{oauthBanner.message}</span>
            <button type="button" onClick={onDismissBanner} className="underline">
              Dismiss
            </button>
          </div>
        )}

        {(!oauthConfigured || !encryptionConfigured) && (
          <div className="rounded-2xl border border-amber-500/35 bg-amber-950/30 p-4 text-xs text-amber-200">
            <div className="flex items-start gap-2.5">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
              <div className="space-y-1">
                <p className="font-semibold">Google OAuth Configuration Required</p>
                <p className="text-amber-200/80">
                  {!oauthConfigured &&
                    "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are not set in backend/.env. "}
                  {!encryptionConfigured &&
                    "TOKEN_ENCRYPTION_KEY is not configured in backend/.env. "}
                  See <code className="text-amber-100">docs/OAUTH_SETUP.md</code> for setup steps.
                </p>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-2.5 text-xs text-rose-200">
            {error}
          </div>
        )}

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Google Workspace (MCP Enabled)
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {activeIntegrations.map((card) => {
              const isConnected = card.status === "connected";
              const needsReconnect = card.status === "needs_reconnect";
              const isGmail = card.provider === "gmail";
              const serviceKey = isGmail ? "gmail" : "calendar";
              const isBusy = busyProvider === serviceKey;

              return (
                <div
                  key={card.provider}
                  className="flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/80 p-5"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
                          {isGmail ? <Mail className="h-5 w-5" /> : <Calendar className="h-5 w-5" />}
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-white">{card.display_name}</h4>
                          <p className="text-xs text-slate-400">
                            {card.account_email ?? "No Google account linked"}
                          </p>
                        </div>
                      </div>

                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                          isConnected
                            ? "bg-emerald-500/15 text-emerald-300"
                            : needsReconnect
                              ? "bg-amber-500/15 text-amber-300"
                              : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {isConnected ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        {isConnected
                          ? "Connected"
                          : needsReconnect
                            ? "Needs Reconnect"
                            : "Disconnected"}
                      </span>
                    </div>

                    <p className="mt-3 text-xs leading-relaxed text-slate-300">
                      {card.description}
                    </p>

                    <div className="mt-3 space-y-1">
                      <p className="text-[11px] font-medium text-slate-400">Permissions:</p>
                      <ul className="space-y-1 text-[11px] text-slate-400">
                        {card.available_permissions.map((perm) => (
                          <li key={perm} className="flex items-center gap-1.5">
                            <ShieldCheck className="h-3 w-3 text-indigo-400" />
                            {perm}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {card.last_connected_at && (
                      <p className="mt-3 text-[11px] text-slate-500">
                        Last connected: {new Date(card.last_connected_at).toLocaleString()}
                      </p>
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-800 pt-4">
                    {!isConnected && !needsReconnect && (
                      <button
                        type="button"
                        disabled={isBusy || !oauthConfigured || !encryptionConfigured}
                        onClick={() => void handleConnect(serviceKey)}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        {isBusy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        Connect {card.display_name}
                      </button>
                    )}

                    {(isConnected || needsReconnect) && (
                      <>
                        <button
                          type="button"
                          disabled={isBusy || !oauthConfigured || !encryptionConfigured}
                          onClick={() => void handleReconnect(serviceKey)}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-45"
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                          Reconnect
                        </button>
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => void handleDisconnect(serviceKey)}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/40 bg-rose-950/40 px-3 py-2 text-xs font-medium text-rose-200 hover:bg-rose-900/50 disabled:opacity-45"
                        >
                          <Unplug className="h-3.5 w-3.5" />
                          Disconnect
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Planned MCP Integrations
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plannedIntegrations.map((card) => (
              <div
                key={card.provider}
                className="rounded-2xl border border-slate-800/80 bg-slate-900/50 p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-slate-500" />
                    <h4 className="text-sm font-medium text-slate-200">{card.display_name}</h4>
                  </div>
                  <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-400 ring-1 ring-slate-700">
                    Coming Soon
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-400">{card.description}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
