import { useCallback, useEffect, useState } from "react";
import { apiClient, ApiError } from "../services/apiClient";
import type { Conversation, HealthResponse, Memory, Task } from "../types/api";

export function useLifeDeskData() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskCounts, setTaskCounts] = useState({ total: 0, pending: 0, completed: 0 });
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  const refreshTasks = useCallback(async (params?: { status?: string; q?: string }) => {
    const res = await apiClient.listTasks(params);
    setTasks(res.tasks);
    setTaskCounts({
      total: res.pending_count + res.completed_count,
      pending: res.pending_count,
      completed: res.completed_count,
    });
  }, []);

  const refreshMemories = useCallback(async () => {
    const res = await apiClient.listMemories();
    setMemories(res.memories);
  }, []);

  const refreshConversations = useCallback(async () => {
    const res = await apiClient.listConversations();
    setConversations(res.conversations);
  }, []);

  const refreshHealth = useCallback(async () => {
    const res = await apiClient.getHealth();
    setHealth(res);
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      await Promise.all([
        refreshHealth(),
        refreshTasks(),
        refreshMemories(),
        refreshConversations(),
      ]);
      setBackendError(null);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Unable to communicate with the LifeDesk AI backend.";
      setBackendError(msg);
    }
  }, [refreshConversations, refreshHealth, refreshMemories, refreshTasks]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  return {
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
    refreshAll,
  };
}
