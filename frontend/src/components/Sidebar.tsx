import {
  Brain,
  CheckSquare,
  Cpu,
  MessageSquare,
  Plus,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import type { Conversation, HealthResponse, NavPage } from "../types/api";

interface SidebarProps {
  activePage: NavPage;
  onSelectPage: (page: NavPage) => void;
  conversations: Conversation[];
  activeConversationId: number | null;
  onSelectConversation: (conversationId: number) => void;
  onNewChat: () => void;
  pendingTaskCount: number;
  memoryCount: number;
  health: HealthResponse | null;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  activePage,
  onSelectPage,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  pendingTaskCount,
  memoryCount,
  health,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const navItems: Array<{
    id: NavPage;
    label: string;
    icon: typeof MessageSquare;
    badge?: number;
  }> = [
    { id: "chat", label: "Chat", icon: MessageSquare },
    { id: "tasks", label: "Tasks", icon: CheckSquare, badge: pendingTaskCount },
    { id: "memory", label: "Memory", icon: Brain, badge: memoryCount },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  const llm = health?.llm;

  const content = (
    <aside className="flex h-full w-72 flex-col border-r border-slate-800 bg-slate-900/95 text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/30">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-white">LifeDesk AI</h1>
            <p className="text-xs text-slate-400">Personal Agent</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onCloseMobile}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
          aria-label="Close sidebar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-3">
        <button
          type="button"
          onClick={() => {
            onNewChat();
            onSelectPage("chat");
            onCloseMobile();
          }}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      <nav className="space-y-1 px-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onSelectPage(item.id);
                onCloseMobile();
              }}
              className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="h-4 w-4" />
                {item.label}
              </span>
              {typeof item.badge === "number" && (
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300 ring-1 ring-slate-700">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="mt-5 flex min-h-0 flex-1 flex-col border-t border-slate-800 px-3 pt-3">
        <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Conversations
        </p>
        <div className="flex-1 space-y-1 overflow-y-auto pb-3">
          {conversations.length === 0 ? (
            <p className="px-2 py-2 text-xs text-slate-500">No conversations yet.</p>
          ) : (
            conversations.map((conv) => {
              const selected = activePage === "chat" && activeConversationId === conv.id;
              return (
                <button
                  key={conv.id}
                  type="button"
                  onClick={() => {
                    onSelectConversation(conv.id);
                    onSelectPage("chat");
                    onCloseMobile();
                  }}
                  className={`w-full truncate rounded-lg px-2.5 py-2 text-left text-xs transition ${
                    selected
                      ? "bg-indigo-500/15 font-medium text-indigo-300 ring-1 ring-indigo-500/30"
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                  }`}
                  title={conv.title}
                >
                  {conv.title}
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="border-t border-slate-800 p-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2.5">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
            <Cpu className="h-3.5 w-3.5 text-indigo-400" />
            <span className="uppercase">{llm?.provider ?? "unknown"}</span>
            <span
              className={`ml-auto h-2 w-2 rounded-full ${
                llm?.configured ? "bg-emerald-400" : "bg-amber-400"
              }`}
              title={llm?.status_message ?? "Checking status"}
            />
          </div>
          <p className="mt-1 truncate text-[11px] text-slate-400" title={llm?.model ?? ""}>
            {llm?.model || "Checking backend..."}
          </p>
        </div>
      </div>
    </aside>
  );

  return (
    <>
      <div className="hidden h-full lg:block">{content}</div>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="fixed inset-0 bg-black/60" onClick={onCloseMobile} />
          <div className="relative z-50 h-full">{content}</div>
        </div>
      )}
    </>
  );
}
