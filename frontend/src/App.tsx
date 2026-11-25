import { useState } from "react";
import { Menu } from "lucide-react";
import { ContextPanel } from "./components/ContextPanel";
import { Sidebar } from "./components/Sidebar";
import { useLifeDeskData } from "./hooks/useLifeDeskData";
import { ChatPage } from "./pages/ChatPage";
import { MemoryPage } from "./pages/MemoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { apiClient, ApiError } from "./services/apiClient";
import type { ChatMessage, NavPage } from "./types/api";

export default function App() {
  const {
    tasks,
    taskCounts,
    memories,
    conversations,
    health,
    backendError,
    setBackendError,
    refreshTasks,
    refreshMemories,
    refreshConversations,
    refreshHealth,
  } = useLifeDeskData();

  const [activePage, setActivePage] = useState<NavPage>("chat");
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [showContext, setShowContext] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

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

      await Promise.all([refreshTasks(), refreshMemories(), refreshConversations()]);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to send message to LifeDesk backend.";
      setChatError(msg);
    } finally {
      setChatLoading(false);
    }
  }

  const displayedError = chatError || backendError;

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
                isLoading={chatLoading}
                error={displayedError}
                onDismissError={() => {
                  setChatError(null);
                  setBackendError(null);
                }}
                onSendMessage={handleSendMessage}
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

          {activePage === "settings" && (
            <SettingsPage health={health} onRefreshHealth={refreshHealth} />
          )}
        </main>
      </div>
    </div>
  );
}
