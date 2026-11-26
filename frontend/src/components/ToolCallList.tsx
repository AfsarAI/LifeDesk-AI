import { CheckCircle2, Clock, Plug, Wrench, XCircle } from "lucide-react";
import type { Approval, ToolExecutionRecord } from "../types/api";

interface ToolCallListProps {
  toolCalls: ToolExecutionRecord[];
  approvalsById?: Map<number, Approval>;
  userTimezone?: string;
  onOpenIntegrations?: () => void;
}

const FRIENDLY_LABELS: Record<string, string> = {
  create_task: "Created task",
  list_tasks: "Checked tasks",
  update_task: "Updated task",
  complete_task: "Completed task",
  search_tasks: "Searched tasks",
  save_memory: "Saved memory",
  retrieve_memory: "Retrieved memory",
  create_reminder: "Created reminder",
  list_reminders: "Checked reminders",
  get_user_preferences: "Loaded user preferences",
  request_user_approval: "Prepared action for approval",
  gmail_search_emails: "Searched Gmail",
  gmail_get_email: "Read email",
  gmail_list_recent_emails: "Listed recent emails",
  gmail_get_thread: "Read Gmail thread",
  gmail_create_draft: "Created Gmail draft",
  gmail_send_email: "Prepared email for approval",
  calendar_list_calendars: "Listed Google Calendars",
  calendar_list_events: "Checked calendar events",
  calendar_get_event: "Read calendar event",
  calendar_check_availability: "Checked calendar availability",
  calendar_find_conflicts: "Checked calendar conflicts",
  calendar_create_event: "Prepared calendar event",
  calendar_update_event: "Prepared calendar update",
  calendar_delete_event: "Prepared calendar deletion",
};

const EXECUTED_APPROVAL_LABELS: Record<string, string> = {
  gmail_send_email: "Sent email",
  calendar_create_event: "Created calendar event",
  calendar_update_event: "Updated calendar event",
  calendar_delete_event: "Deleted calendar event",
};

function formatShortWindow(startRaw: unknown, endRaw: unknown, tz = "UTC"): string | null {
  if (typeof startRaw !== "string" || typeof endRaw !== "string") return null;
  const start = new Date(startRaw);
  const end = new Date(endRaw);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
  try {
    const dateFmt = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    const timeFmt = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hour: "numeric",
      minute: "2-digit",
    });
    return `${dateFmt.format(start)} • ${timeFmt.format(start)} – ${timeFmt.format(end)}`;
  } catch {
    return null;
  }
}

function summarizeToolArgs(call: ToolExecutionRecord, userTimezone: string): string | null {
  const args = call.arguments || {};
  switch (call.tool_name) {
    case "gmail_search_emails":
      return typeof args.query === "string" ? `Query: "${args.query}"` : null;
    case "gmail_create_draft":
    case "gmail_send_email": {
      const parts: string[] = [];
      if (typeof args.to === "string") parts.push(`To: ${args.to}`);
      if (typeof args.subject === "string") parts.push(`Subject: ${args.subject}`);
      if (typeof args.thread_id === "string" && args.thread_id) parts.push("In thread");
      return parts.length > 0 ? parts.join(" • ") : null;
    }
    case "calendar_list_events":
    case "calendar_check_availability":
    case "calendar_find_conflicts":
      return formatShortWindow(args.start_datetime, args.end_datetime, userTimezone);
    case "calendar_create_event":
    case "calendar_update_event": {
      const parts: string[] = [];
      if (typeof args.title === "string") parts.push(args.title);
      const win = formatShortWindow(args.start_datetime, args.end_datetime, userTimezone);
      if (win) parts.push(win);
      return parts.length > 0 ? parts.join(" • ") : null;
    }
    case "create_task":
    case "update_task":
    case "create_reminder":
      return typeof args.title === "string" ? args.title : null;
    case "search_tasks":
      return typeof args.query === "string" ? `Query: "${args.query}"` : null;
    case "save_memory":
    case "retrieve_memory":
      return typeof args.key === "string" ? `Key: ${args.key}` : null;
    case "request_user_approval":
      return typeof args.summary === "string" ? args.summary : null;
    default:
      return null;
  }
}

export function getRecordApprovalId(call: ToolExecutionRecord): number | null {
  if (typeof call.approval_id === "number") return call.approval_id;
  if (typeof call.result?.approval_id === "number") return call.result.approval_id;
  return null;
}

export function ToolCallList({
  toolCalls,
  approvalsById,
  userTimezone = "UTC",
  onOpenIntegrations,
}: ToolCallListProps) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="mb-2.5 space-y-1.5">
      {toolCalls.map((call, idx) => {
        const approvalId = getRecordApprovalId(call);
        const liveApproval = approvalId !== null ? approvalsById?.get(approvalId) : undefined;
        const wasApprovalStaged = call.result?.status === "approval_required" || approvalId !== null;
        const liveStatus = liveApproval?.status;

        const isStillPending = wasApprovalStaged
          ? liveApproval
            ? liveStatus === "PENDING"
            : true
          : false;

        const isExecuted = liveStatus === "EXECUTED" || (!wasApprovalStaged && call.success);
        const isRejectedOrCancelled =
          liveStatus === "REJECTED" || liveStatus === "CANCELLED" || liveStatus === "EXPIRED";
        const isFailed =
          liveStatus === "FAILED" || (!wasApprovalStaged && !call.success);

        const needsIntegration =
          call.result?.error_code === "integration_required" ||
          call.result?.error_code === "integration_auth_error";

        const label =
          liveStatus === "EXECUTED" && EXECUTED_APPROVAL_LABELS[call.tool_name]
            ? EXECUTED_APPROVAL_LABELS[call.tool_name]
            : FRIENDLY_LABELS[call.tool_name] ?? call.tool_name.replaceAll("_", " ");
        const summaryLine = summarizeToolArgs(call, userTimezone);

        const errorText =
          liveStatus === "FAILED" && typeof liveApproval?.execution_result?.error === "string"
            ? liveApproval.execution_result.error
            : !call.success && typeof call.result?.error === "string"
              ? call.result.error
              : null;

        return (
          <div
            key={`${call.call_id || call.tool_name}-${idx}`}
            className={`rounded-xl border px-3 py-2 text-xs ${
              isStillPending
                ? "border-amber-500/35 bg-amber-950/30 text-amber-200"
                : isExecuted
                  ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-200"
                  : isRejectedOrCancelled
                    ? "border-slate-700 bg-slate-900/70 text-slate-300"
                    : "border-rose-500/30 bg-rose-950/30 text-rose-200"
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              <Wrench className="h-3.5 w-3.5 shrink-0 opacity-80" />
              <span>{label}</span>
              <span className="ml-auto flex items-center gap-1 text-[11px]">
                {isStillPending ? (
                  <>
                    <Clock className="h-3.5 w-3.5 text-amber-400" />
                    Awaiting Approval
                  </>
                ) : isExecuted ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    {liveStatus === "EXECUTED" ? "Executed" : "Done"}
                  </>
                ) : liveStatus === "REJECTED" ? (
                  <>
                    <XCircle className="h-3.5 w-3.5 text-slate-400" />
                    Rejected
                  </>
                ) : liveStatus === "CANCELLED" ? (
                  <>
                    <XCircle className="h-3.5 w-3.5 text-slate-400" />
                    Superseded
                  </>
                ) : liveStatus === "EXPIRED" ? (
                  <>
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                    Expired
                  </>
                ) : isFailed ? (
                  <>
                    <XCircle className="h-3.5 w-3.5 text-rose-400" />
                    Failed
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    Done
                  </>
                )}
              </span>
            </div>
            {summaryLine && <p className="mt-1 truncate text-[11px] opacity-85">{summaryLine}</p>}
            {errorText && (
              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-rose-300">
                <span>{errorText}</span>
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
