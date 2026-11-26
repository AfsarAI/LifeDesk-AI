import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Bot,
  Loader2,
  PanelRightOpen,
  Plug,
  Send,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { ApprovalCard } from "../components/ApprovalCard";
import { ToolCallList } from "../components/ToolCallList";
import type { Approval, ChatMessage } from "../types/api";

interface ChatPageProps {
  messages: ChatMessage[];
  pendingApprovals: Approval[];
  recentApprovals: Approval[];
  isLoading: boolean;
  error: string | null;
  onDismissError: () => void;
  onSendMessage: (message: string) => Promise<void>;
  onApproveAction: (approvalId: number) => Promise<void>;
  onRejectAction: (approvalId: number) => Promise<void>;
  onEditDraftApproval: (
    approval: Approval,
    edited: { to: string; subject: string; body: string }
  ) => Promise<void>;
  onOpenIntegrations: () => void;
  showContextToggle: boolean;
  onShowContext: () => void;
}

const STARTER_PROMPTS = [
  "Give me my daily briefing.",
  "Find the email from Rahul about tomorrow's meeting and add it to my calendar.",
  "Draft a reply to Rahul confirming the meeting.",
  "Schedule my pending tasks across my free time tomorrow.",
  "Create a task called Complete my DSA assignment.",
];

export function ChatPage({
  messages,
  pendingApprovals,
  recentApprovals,
  isLoading,
  error,
  onDismissError,
  onSendMessage,
  onApproveAction,
  onRejectAction,
  onEditDraftApproval,
  onOpenIntegrations,
  showContextToggle,
  onShowContext,
}: ChatPageProps) {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  const visibleMessages = messages.filter((m) => m.role === "user" || m.role === "assistant");
  const displayedApprovals = [
    ...pendingApprovals,
    ...recentApprovals.filter((r) => !pendingApprovals.some((p) => p.id === r.id)),
  ].slice(0, 5);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleMessages.length, displayedApprovals.length, isLoading]);

  async function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    setInput("");
    await onSendMessage(trimmed);
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-slate-800 px-5 py-3.5">
        <div>
          <h2 className="text-sm font-semibold text-white">Assistant Chat</h2>
          <p className="text-xs text-slate-400">
            Tasks, Memory, Gmail & Google Calendar with human approval gates
          </p>
        </div>
        {showContextToggle && (
          <button
            type="button"
            onClick={onShowContext}
            className="hidden items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1.5 text-xs text-slate-200 hover:bg-slate-800 xl:flex"
          >
            <PanelRightOpen className="h-3.5 w-3.5" />
            Context
          </button>
        )}
      </header>

      {error && (
        <div className="mx-5 mt-3 flex items-start gap-2.5 rounded-xl border border-rose-500/40 bg-rose-950/50 px-3.5 py-2.5 text-xs text-rose-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
          <span className="flex-1">{error}</span>
          {error.toLowerCase().includes("connect") && (
            <button
              type="button"
              onClick={onOpenIntegrations}
              className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-indigo-500"
            >
              <Plug className="h-3 w-3" />
              Integrations
            </button>
          )}
          <button
            type="button"
            onClick={onDismissError}
            className="rounded p-0.5 text-rose-300 hover:bg-rose-900/50"
            aria-label="Dismiss error"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
        {visibleMessages.length === 0 && displayedApprovals.length === 0 ? (
          <div className="mx-auto flex max-w-2xl flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/15 text-indigo-400 ring-1 ring-indigo-500/30">
              <Sparkles className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-semibold text-white">Your Personal AI Chief of Staff</h3>
            <p className="mt-1.5 max-w-md text-sm text-slate-400">
              Coordinate Gmail, Google Calendar, tasks, and long-term memory—with explicit approval
              before sending emails or modifying calendar events.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={isLoading}
                  onClick={() => void onSendMessage(prompt)}
                  className="rounded-xl border border-slate-800 bg-slate-900/80 px-3.5 py-2 text-left text-xs text-slate-300 transition hover:border-indigo-500/50 hover:bg-slate-800 hover:text-white disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-5">
            {visibleMessages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
                >
                  {!isUser && (
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/30">
                      <Bot className="h-4 w-4" />
                    </div>
                  )}
                  <div
                    className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      isUser
                        ? "bg-indigo-600 text-white"
                        : "border border-slate-800 bg-slate-900/90 text-slate-100"
                    }`}
                  >
                    {!isUser && (
                      <ToolCallList
                        toolCalls={msg.tool_calls}
                        onOpenIntegrations={onOpenIntegrations}
                      />
                    )}
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  {isUser && (
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-slate-300 ring-1 ring-slate-700">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </div>
              );
            })}

            {displayedApprovals.length > 0 && (
              <div className="space-y-3 pt-2">
                {displayedApprovals.map((approval) => (
                  <ApprovalCard
                    key={approval.id}
                    approval={approval}
                    onApprove={onApproveAction}
                    onReject={onRejectAction}
                    onEditDraft={onEditDraftApproval}
                  />
                ))}
              </div>
            )}

            {isLoading && (
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/30">
                  <Loader2 className="h-4 w-4 animate-spin" />
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-xs text-slate-300">
                  Agent is orchestrating native and MCP tools...
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="border-t border-slate-800 bg-slate-950/90 px-5 py-4">
        <div className="mx-auto flex max-w-3xl items-end gap-3 rounded-2xl border border-slate-800 bg-slate-900 p-2.5 focus-within:border-indigo-500/60">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSubmit();
              }
            }}
            placeholder="Message LifeDesk AI... (Enter to send, Shift+Enter for new line)"
            className="max-h-36 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none"
          />
          <button
            type="button"
            disabled={isLoading || !input.trim()}
            onClick={() => void handleSubmit()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Send message"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
