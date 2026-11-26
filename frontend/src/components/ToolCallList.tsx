import { CheckCircle2, Clock, Plug, Wrench, XCircle } from "lucide-react";
import type { ToolExecutionRecord } from "../types/api";

interface ToolCallListProps {
  toolCalls: ToolExecutionRecord[];
  onOpenIntegrations?: () => void;
}

const FRIENDLY_LABELS: Record<string, string> = {
  gmail_search_emails: "Searched Gmail",
  gmail_get_email: "Read email details",
  gmail_list_recent_emails: "Listed recent emails",
  gmail_get_thread: "Read Gmail thread",
  gmail_create_draft: "Created Gmail draft",
  gmail_send_email: "Waiting for approval to send email",
  calendar_list_calendars: "Listed Google Calendars",
  calendar_list_events: "Checked calendar events",
  calendar_get_event: "Read calendar event",
  calendar_check_availability: "Checked calendar availability",
  calendar_find_conflicts: "Checked calendar conflicts",
  calendar_create_event: "Waiting for approval to create event",
  calendar_update_event: "Waiting for approval to update event",
  calendar_delete_event: "Waiting for approval to delete event",
};

export function ToolCallList({ toolCalls, onOpenIntegrations }: ToolCallListProps) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="mb-2.5 space-y-1.5">
      {toolCalls.map((call, idx) => {
        const isApprovalRequired = call.result?.status === "approval_required";
        const needsIntegration =
          call.result?.error_code === "integration_required" ||
          call.result?.error_code === "integration_auth_error";
        const label = FRIENDLY_LABELS[call.tool_name] ?? call.tool_name;

        return (
          <div
            key={`${call.call_id || call.tool_name}-${idx}`}
            className={`rounded-xl border px-3 py-2 text-xs ${
              isApprovalRequired
                ? "border-amber-500/35 bg-amber-950/30 text-amber-200"
                : call.success
                  ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-200"
                  : "border-rose-500/30 bg-rose-950/30 text-rose-200"
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              <Wrench className="h-3.5 w-3.5 shrink-0 opacity-80" />
              <span>{label}</span>
              {call.tool_source && (
                <span className="rounded bg-slate-900/70 px-1.5 py-0.5 font-mono text-[10px] uppercase opacity-75">
                  {call.tool_source}
                </span>
              )}
              <span className="ml-auto flex items-center gap-1 text-[11px]">
                {isApprovalRequired ? (
                  <>
                    <Clock className="h-3.5 w-3.5 text-amber-400" />
                    Pending Approval
                  </>
                ) : call.success ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    Executed
                  </>
                ) : (
                  <>
                    <XCircle className="h-3.5 w-3.5 text-rose-400" />
                    Failed
                  </>
                )}
              </span>
            </div>
            {Object.keys(call.arguments).length > 0 && (
              <p className="mt-1 truncate font-mono text-[11px] opacity-80">
                {call.tool_name}: {JSON.stringify(call.arguments)}
              </p>
            )}
            {!call.success && typeof call.result?.error === "string" && (
              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-rose-300">
                <span>{call.result.error}</span>
                {needsIntegration && onOpenIntegrations && (
                  <button
                    type="button"
                    onClick={onOpenIntegrations}
                    className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-indigo-500"
                  >
                    <Plug className="h-3 w-3" />
                    Connect Google
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
