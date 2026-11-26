import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { ContextPanel } from "./components/ContextPanel";
import { Sidebar } from "./components/Sidebar";
import { useLifeDeskData } from "./hooks/useLifeDeskData";
import { ChatPage } from "./pages/ChatPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { MemoryPage } from "./pages/MemoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { apiClient, ApiError } from "./services/apiClient";
import type { Approval, ChatMessage, NavPage } from "./types/api";

export default function App() {
  const {
    tasks,
    taskCounts,
    memories,
    conversations,
    integrations,
    oauthConfigured,
    encryptionConfigured,
    approvals,
    pendingApprovalCount,
    currentUser,
    users,
    health,
    backendError,
    setBackendError,
    refreshTasks,
    refreshMemories,
    refreshConversations,
    refreshIntegrations,
    refreshApprovals,
    refreshHealth,
    refreshAll,
  } = useLifeDeskData();

  const [activePage, setActivePage] = useState<NavPage>("chat");
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [showContext, setShowContext] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [oauthBanner, setOauthBanner] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const page = params.get("page");
    const oauthStatus = params.get("oauth");
    if (page === "integrations") {
      setActivePage("integrations");
    }
    if (oauthStatus === "connected") {
      const service = params.get("service") || "google";
      setOauthBanner({
        type: "success",
        message: `Google (${service}) connected successfully.`,
      });
      void refreshIntegrations();
      window.history.replaceState({}, "", "/");
    } else if (oauthStatus === "error") {
      const reason = params.get("reason") || "Google authorization was cancelled or failed.";
      setOauthBanner({ type: "error", message: reason });
      window.history.replaceState({}, "", "/");
    }
  }, [refreshIntegrations]);

  async function handleSelectConversation(conversationId: number) {
    setActiveConversationId(conversationId);
    setChatError(null);
    try {
      const res = await apiClient.getConversationMessages(conversationId);
      setMessages(res.messages);
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Failed to load conversation.");
    }
  }

  function handleNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setChatError(null);
  }

  async function handleSendMessage(text: string) {
    setChatError(null);
    setChatLoading(true);

    const optimisticUser: ChatMessage = {
      id: Date.now(),
      conversation_id: activeConversationId ?? 0,
      role: "user",
      content: text,
      tool_calls: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);

    try {
      const res = await apiClient.sendChat(text, activeConversationId);
      setActiveConversationId(res.conversation_id);

      const history = await apiClient.getConversationMessages(res.conversation_id);
      setMessages(history.messages);

      await Promise.all([
        refreshTasks(),
        refreshMemories(),
        refreshConversations(),
        refreshApprovals(),
      ]);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to send message to LifeDesk backend.";
      setChatError(msg);
    } finally {
      setChatLoading(false);
    }
  }

  async function handleApproveAction(approvalId: number) {
    setChatError(null);
    try {
      await apiClient.approveAction(approvalId);
      await Promise.all([refreshApprovals(), refreshIntegrations()]);
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Failed to approve action.");
    }
  }

  async function handleRejectAction(approvalId: number) {
    setChatError(null);
    try {
      await apiClient.rejectAction(approvalId);
      await refreshApprovals();
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Failed to reject action.");
    }
  }

  async function handleEditDraftApproval(
    approval: Approval,
    edited: { to: string; subject: string; body: string }
  ) {
    setChatError(null);
    await apiClient.rejectAction(approval.id);
    await refreshApprovals();
    await handleSendMessage(
      `Create a Gmail draft (or propose sending with new approval) to ${edited.to} with subject "${edited.subject}" and body:\n${edited.body}`
    );
  }

  const displayedError = chatError || backendError;
  const connectedIntegrationCount = integrations.filter((i) => i.status === "connected").length;
  const pendingApprovals = approvals.filter((a) => a.status === "PENDING");
  const recentApprovals = approvals.filter((a) => a.status !== "PENDING");

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      <Sidebar
        activePage={activePage}
        onSelectPage={setActivePage}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={(id) => void handleSelectConversation(id)}
        onNewChat={handleNewChat}
        pendingTaskCount={taskCounts.pending}
        memoryCount={memories.length}
        connectedIntegrationCount={connectedIntegrationCount}
        pendingApprovalCount={pendingApprovalCount}
        currentUser={currentUser}
        health={health}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2.5 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(true)}
            className="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold text-white">LifeDesk AI</span>
          <span className="w-8" />
        </div>

        <main className="flex min-h-0 flex-1 overflow-hidden">
          {activePage === "chat" && (
            <>
              <ChatPage
                messages={messages}
                pendingApprovals={pendingApprovals}
                recentApprovals={recentApprovals}
                isLoading={chatLoading}
                error={displayedError}
                onDismissError={() => {
                  setChatError(null);
                  setBackendError(null);
                }}
                onSendMessage={handleSendMessage}
                onApproveAction={handleApproveAction}
                onRejectAction={handleRejectAction}
                onEditDraftApproval={handleEditDraftApproval}
                onOpenIntegrations={() => setActivePage("integrations")}
                showContextToggle={!showContext}
                onShowContext={() => setShowContext(true)}
              />
              {showContext && (
                <ContextPanel
                  tasks={tasks}
                  memories={memories}
                  onClose={() => setShowContext(false)}
                  onOpenTasks={() => setActivePage("tasks")}
                  onOpenMemory={() => setActivePage("memory")}
                />
              )}
            </>
          )}

          {activePage === "tasks" && (
            <TasksPage tasks={tasks} counts={taskCounts} onRefresh={refreshTasks} />
          )}

          {activePage === "memory" && (
            <MemoryPage memories={memories} onRefresh={refreshMemories} />
          )}

          {activePage === "integrations" && (
            <IntegrationsPage
              integrations={integrations}
              oauthConfigured={oauthConfigured}
              encryptionConfigured={encryptionConfigured}
              oauthBanner={oauthBanner}
              onDismissBanner={() => setOauthBanner(null)}
              onRefresh={refreshIntegrations}
            />
          )}

          {activePage === "settings" && (
            <SettingsPage
              health={health}
              currentUser={currentUser}
              users={users}
              onRefreshHealth={refreshHealth}
              onUserChanged={async () => {
                handleNewChat();
                await refreshAll();
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
