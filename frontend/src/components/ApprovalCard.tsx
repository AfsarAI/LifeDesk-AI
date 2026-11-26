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
  onApprove: (approvalId: number) => Promise<void>;
  onReject: (approvalId: number) => Promise<void>;
  onEditDraft?: (approval: Approval, edited: { to: string; subject: string; body: string }) => Promise<void>;
}

export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  onEditDraft,
}: ApprovalCardProps) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const payload = approval.action_payload;

  const [draftTo, setDraftTo] = useState(String(payload.to ?? ""));
  const [draftSubject, setDraftSubject] = useState(String(payload.subject ?? ""));
  const [draftBody, setDraftBody] = useState(String(payload.body ?? ""));

  const isEmail = approval.tool_name === "gmail_send_email";
  const isCalendar = approval.provider === "calendar";
  const isPending = approval.status === "PENDING";

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

  const titleLabel =
    approval.tool_name === "gmail_send_email"
      ? "Send Email"
      : approval.tool_name === "calendar_create_event"
        ? "Create Google Calendar Event"
        : approval.tool_name === "calendar_update_event"
          ? "Update Google Calendar Event"
          : approval.tool_name === "calendar_delete_event"
            ? "Delete Google Calendar Event"
            : approval.summary;

  return (
    <div className="rounded-2xl border border-amber-500/35 bg-slate-900/95 p-4 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/15 text-amber-300">
            {isEmail ? (
              <Mail className="h-4 w-4" />
            ) : isCalendar ? (
              <Calendar className="h-4 w-4" />
            ) : (
              <ShieldAlert className="h-4 w-4" />
            )}
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">{titleLabel}</h4>
            <p className="text-[11px] text-slate-400">
              Approval #{approval.id} • {approval.provider}
            </p>
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
          {approval.status}
        </span>
      </div>

      <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-200">
        {isEmail && !editing && (
          <div className="space-y-1.5">
            <p>
              <span className="text-slate-400">To:</span> {String(payload.to ?? "")}
            </p>
            <p>
              <span className="text-slate-400">Subject:</span> {String(payload.subject ?? "")}
            </p>
            <div className="mt-2 border-t border-slate-800 pt-2">
              <p className="mb-1 text-slate-400">Body:</p>
              <p className="whitespace-pre-wrap text-slate-100">{String(payload.body ?? "")}</p>
            </div>
          </div>
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
              Editing rejects this request and creates a fresh proposal requiring new approval.
            </p>
          </div>
        )}

        {isCalendar && (
          <div className="space-y-1">
            {Boolean(payload.title) && (
              <p>
                <span className="text-slate-400">Title:</span> {String(payload.title)}
              </p>
            )}
            {Boolean(payload.event_id) && (
              <p>
                <span className="text-slate-400">Event ID:</span>{" "}
                <span className="font-mono">{String(payload.event_id)}</span>
              </p>
            )}
            {Boolean(payload.start_datetime) && (
              <p>
                <span className="text-slate-400">Start:</span> {String(payload.start_datetime)}
              </p>
            )}
            {Boolean(payload.end_datetime) && (
              <p>
                <span className="text-slate-400">End:</span> {String(payload.end_datetime)}
              </p>
            )}
            {Array.isArray(payload.attendees) && payload.attendees.length > 0 && (
              <p>
                <span className="text-slate-400">Attendees:</span>{" "}
                {payload.attendees.map(String).join(", ")}
              </p>
            )}
            {Boolean(payload.description) && (
              <p className="text-slate-300">
                <span className="text-slate-400">Description:</span> {String(payload.description)}
              </p>
            )}
          </div>
        )}

        {!isEmail && !isCalendar && <p>{approval.summary}</p>}
      </div>

      {approval.execution_result && (
        <div
          className={`mt-2.5 rounded-xl px-3 py-2 text-xs ${
            approval.status === "EXECUTED"
              ? "bg-emerald-950/40 text-emerald-200"
              : "bg-rose-950/40 text-rose-200"
          }`}
        >
          {typeof approval.execution_result.error === "string"
            ? approval.execution_result.error
            : approval.status === "EXECUTED"
              ? "Action executed successfully."
              : JSON.stringify(approval.execution_result)}
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
