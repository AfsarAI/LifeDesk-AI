import { useState } from "react";
import {
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Edit3,
  Loader2,
  Mail,
  ShieldAlert,
  X,
  XCircle,
} from "lucide-react";
import type { Approval } from "../types/api";

interface ApprovalCardProps {
  approval: Approval;
  userTimezone?: string;
  onApprove: (approvalId: number) => Promise<void>;
  onReject: (approvalId: number) => Promise<void>;
  onEditDraft?: (
    approval: Approval,
    edited: { to: string; subject: string; body: string }
  ) => Promise<void>;
}

function unescapeBody(raw: unknown): string {
  if (typeof raw !== "string") return "";
  return raw.replace(/\\n/g, "\n");
}

function formatCalendarSchedule(
  startRaw: unknown,
  endRaw: unknown,
  userTimezone: string
): { dateLabel: string; timeLabel: string; durationLabel: string | null } | null {
  if (typeof startRaw !== "string") return null;
  const start = new Date(startRaw);
  if (Number.isNaN(start.getTime())) return null;

  const end = typeof endRaw === "string" ? new Date(endRaw) : null;
  const hasValidEnd = end !== null && !Number.isNaN(end.getTime());

  try {
    const dateFmt = new Intl.DateTimeFormat("en-US", {
      timeZone: userTimezone,
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    const timeFmt = new Intl.DateTimeFormat("en-US", {
      timeZone: userTimezone,
      hour: "numeric",
      minute: "2-digit",
    });
    const tzFmt = new Intl.DateTimeFormat("en-US", {
      timeZone: userTimezone,
      timeZoneName: "short",
    });
    const tzPart = tzFmt.formatToParts(start).find((p) => p.type === "timeZoneName")?.value ?? userTimezone;

    const dateLabel = dateFmt.format(start);
    const timeLabel = hasValidEnd
      ? `${timeFmt.format(start)} – ${timeFmt.format(end!)} (${tzPart})`
      : `${timeFmt.format(start)} (${tzPart})`;

    let durationLabel: string | null = null;
    if (hasValidEnd) {
      const mins = Math.round((end!.getTime() - start.getTime()) / 60000);
      if (mins > 0) {
        const hrs = Math.floor(mins / 60);
        const rem = mins % 60;
        if (hrs > 0 && rem > 0) durationLabel = `${hrs} hr ${rem} min`;
        else if (hrs > 0) durationLabel = hrs === 1 ? "1 hour" : `${hrs} hours`;
        else durationLabel = `${mins} min`;
      }
    }

    return { dateLabel, timeLabel, durationLabel };
  } catch {
    return null;
  }
}

function formatExecutionOutcome(approval: Approval): string {
  const res = approval.execution_result;
  if (res && typeof res.error === "string") return res.error;
  if (approval.status === "EXECUTED") {
    if (approval.tool_name === "gmail_send_email") {
      return approval.action_payload.thread_id
        ? "Reply sent in the existing Gmail thread."
        : "Email sent via Gmail.";
    }
    if (approval.tool_name === "calendar_create_event") return "Google Calendar event created.";
    if (approval.tool_name === "calendar_update_event") return "Google Calendar event updated.";
    if (approval.tool_name === "calendar_delete_event") return "Google Calendar event deleted.";
    return "Action executed successfully.";
  }
  if (approval.status === "REJECTED") return "Action rejected by user.";
  if (approval.status === "EXPIRED") return "Approval expired before confirmation.";
  return "Action could not be completed.";
}

export function ApprovalCard({
  approval,
  userTimezone = "UTC",
  onApprove,
  onReject,
  onEditDraft,
}: ApprovalCardProps) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);

  // Support payloads produced either directly or via request_user_approval wrapper.
  const payload: Record<string, unknown> =
    typeof approval.action_payload.action_payload === "object" &&
    approval.action_payload.action_payload !== null
      ? (approval.action_payload.action_payload as Record<string, unknown>)
      : approval.action_payload;

  const [draftTo, setDraftTo] = useState(String(payload.to ?? ""));
  const [draftSubject, setDraftSubject] = useState(String(payload.subject ?? ""));
  const [draftBody, setDraftBody] = useState(unescapeBody(payload.body));

  const isEmail =
    approval.tool_name === "gmail_send_email" || approval.action_type === "send_email";
  const isCalendar =
    approval.provider === "calendar" || approval.tool_name.startsWith("calendar_");
  const isPending = approval.status === "PENDING";
  const isThreadReply = Boolean(payload.thread_id);

  async function handleApprove() {
    setBusy(true);
    try {
      await onApprove(approval.id);
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    setBusy(true);
    try {
      await onReject(approval.id);
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveEditedDraft() {
    if (!onEditDraft) return;
    setBusy(true);
    try {
      await onEditDraft(approval, {
        to: draftTo.trim(),
        subject: draftSubject.trim(),
        body: draftBody,
      });
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  const actionTitle = isEmail
    ? isThreadReply
      ? "Reply in Gmail Thread"
      : "Send Email"
    : approval.tool_name === "calendar_create_event"
      ? "Create Google Calendar Event"
      : approval.tool_name === "calendar_update_event"
        ? "Update Google Calendar Event"
        : approval.tool_name === "calendar_delete_event"
          ? "Delete Google Calendar Event"
          : "Confirm Action";

  const providerLabel = isEmail ? "Gmail" : isCalendar ? "Google Calendar" : "LifeDesk";
  const schedule = isCalendar
    ? formatCalendarSchedule(payload.start_datetime, payload.end_datetime, userTimezone)
    : null;

  return (
    <div
      className={`rounded-2xl border p-4 shadow-lg ${
        isPending
          ? "border-amber-500/40 bg-slate-900/95"
          : approval.status === "EXECUTED"
            ? "border-emerald-500/30 bg-slate-900/80"
            : "border-slate-800 bg-slate-900/75"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-xl ${
              isPending
                ? "bg-amber-500/15 text-amber-300"
                : approval.status === "EXECUTED"
                  ? "bg-emerald-500/15 text-emerald-300"
                  : "bg-slate-800 text-slate-400"
            }`}
          >
            {isEmail ? (
              <Mail className="h-4 w-4" />
            ) : isCalendar ? (
              <Calendar className="h-4 w-4" />
            ) : (
              <ShieldAlert className="h-4 w-4" />
            )}
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">{actionTitle}</h4>
            <p className="text-[11px] text-slate-400">{providerLabel}</p>
          </div>
        </div>

        <span
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
            approval.status === "EXECUTED"
              ? "bg-emerald-500/15 text-emerald-300"
              : approval.status === "PENDING"
                ? "bg-amber-500/15 text-amber-300"
                : "bg-rose-500/15 text-rose-300"
          }`}
        >
          {approval.status === "EXECUTED" && <CheckCircle2 className="h-3 w-3" />}
          {approval.status === "PENDING" && <Clock className="h-3 w-3" />}
          {(approval.status === "REJECTED" ||
            approval.status === "FAILED" ||
            approval.status === "EXPIRED") && <XCircle className="h-3 w-3" />}
          {approval.status === "PENDING"
            ? "Awaiting Approval"
            : approval.status === "EXECUTED"
              ? "Executed"
              : approval.status === "REJECTED"
                ? "Rejected"
                : approval.status}
        </span>
      </div>

      <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/75 p-3.5 text-xs text-slate-200">
        {isEmail && !editing && (
          <dl className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <dt className="w-16 shrink-0 font-medium text-slate-400">Action</dt>
              <dd className="text-slate-100">
                {isThreadReply ? "Reply in existing thread" : "Send new email"}
              </dd>
            </div>
            <div className="flex flex-wrap gap-2">
              <dt className="w-16 shrink-0 font-medium text-slate-400">To</dt>
              <dd className="text-slate-100">{String(payload.to ?? "—")}</dd>
            </div>
            <div className="flex flex-wrap gap-2">
              <dt className="w-16 shrink-0 font-medium text-slate-400">Subject</dt>
              <dd className="font-medium text-white">{String(payload.subject ?? "(no subject)")}</dd>
            </div>
            <div className="border-t border-slate-800 pt-2">
              <dt className="mb-1 font-medium text-slate-400">Message</dt>
              <dd className="whitespace-pre-wrap leading-relaxed text-slate-100">
                {unescapeBody(payload.body)}
              </dd>
            </div>
          </dl>
        )}

        {isEmail && editing && (
          <div className="space-y-2.5">
            <input
              type="email"
              value={draftTo}
              onChange={(e) => setDraftTo(e.target.value)}
              placeholder="Recipient"
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-white"
            />
            <input
              type="text"
              value={draftSubject}
              onChange={(e) => setDraftSubject(e.target.value)}
              placeholder="Subject"
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-white"
            />
            <textarea
              rows={4}
              value={draftBody}
              onChange={(e) => setDraftBody(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-white"
            />
            <p className="text-[11px] text-amber-300">
              Editing rejects this request and creates a new proposal requiring fresh approval.
            </p>
          </div>
        )}

        {isCalendar && (
          <dl className="space-y-2">
            {Boolean(payload.title) && (
              <div className="flex flex-wrap gap-2">
                <dt className="w-24 shrink-0 font-medium text-slate-400">Event Title</dt>
                <dd className="font-medium text-white">{String(payload.title)}</dd>
              </div>
            )}
            {schedule ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <dt className="w-24 shrink-0 font-medium text-slate-400">Date</dt>
                  <dd className="text-slate-100">{schedule.dateLabel}</dd>
                </div>
                <div className="flex flex-wrap gap-2">
                  <dt className="w-24 shrink-0 font-medium text-slate-400">Time</dt>
                  <dd className="text-slate-100">{schedule.timeLabel}</dd>
                </div>
                {schedule.durationLabel && (
                  <div className="flex flex-wrap gap-2">
                    <dt className="w-24 shrink-0 font-medium text-slate-400">Duration</dt>
                    <dd className="text-slate-100">{schedule.durationLabel}</dd>
                  </div>
                )}
              </>
            ) : (
              <>
                {Boolean(payload.start_datetime) && (
                  <div className="flex flex-wrap gap-2">
                    <dt className="w-24 shrink-0 font-medium text-slate-400">Start</dt>
                    <dd className="text-slate-100">{String(payload.start_datetime)}</dd>
                  </div>
                )}
                {Boolean(payload.end_datetime) && (
                  <div className="flex flex-wrap gap-2">
                    <dt className="w-24 shrink-0 font-medium text-slate-400">End</dt>
                    <dd className="text-slate-100">{String(payload.end_datetime)}</dd>
                  </div>
                )}
              </>
            )}
            {Array.isArray(payload.attendees) && payload.attendees.length > 0 && (
              <div className="flex flex-wrap gap-2">
                <dt className="w-24 shrink-0 font-medium text-slate-400">Attendees</dt>
                <dd className="text-slate-100">{payload.attendees.map(String).join(", ")}</dd>
              </div>
            )}
            {Boolean(payload.description) && (
              <div className="flex flex-wrap gap-2">
                <dt className="w-24 shrink-0 font-medium text-slate-400">Description</dt>
                <dd className="whitespace-pre-wrap text-slate-300">
                  {unescapeBody(payload.description)}
                </dd>
              </div>
            )}
          </dl>
        )}

        {!isEmail && !isCalendar && <p>{approval.summary}</p>}
      </div>

      {!isPending && (
        <div
          className={`mt-2.5 rounded-xl px-3 py-2 text-xs ${
            approval.status === "EXECUTED"
              ? "bg-emerald-950/40 text-emerald-200"
              : "bg-slate-800/80 text-slate-300"
          }`}
        >
          {formatExecutionOutcome(approval)}
        </div>
      )}

      {isPending && (
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          {isEmail && !editing && onEditDraft && (
            <button
              type="button"
              disabled={busy}
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              <Edit3 className="h-3.5 w-3.5" />
              Edit Draft
            </button>
          )}
          {editing ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(false)}
                className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs text-slate-300"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || !draftTo.trim() || !draftSubject.trim()}
                onClick={() => void handleSaveEditedDraft()}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Re-propose Edited Email
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleReject()}
                className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/40 bg-rose-950/40 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-900/50 disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" />
                Reject
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleApprove()}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {busy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Check className="h-3.5 w-3.5" />
                )}
                {isEmail ? "Approve and Send" : "Approve"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
