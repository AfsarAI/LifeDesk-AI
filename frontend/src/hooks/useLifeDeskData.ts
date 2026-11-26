import { useCallback, useEffect, useState } from "react";
import { apiClient, ApiError } from "../services/apiClient";
import type {
  Approval,
  Conversation,
  HealthResponse,
  IntegrationCard,
  Memory,
  Task,
  UserProfile,
} from "../types/api";

export function useLifeDeskData() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskCounts, setTaskCounts] = useState({ total: 0, pending: 0, completed: 0 });
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationCard[]>([]);
  const [oauthConfigured, setOauthConfigured] = useState(false);
  const [encryptionConfigured, setEncryptionConfigured] = useState(false);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [pendingApprovalCount, setPendingApprovalCount] = useState(0);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [users, setUsers] = useState<UserProfile[]>([]);
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

  const refreshIntegrations = useCallback(async () => {
    const res = await apiClient.listIntegrations();
    setIntegrations(res.integrations);
    setOauthConfigured(res.oauth_configured);
    setEncryptionConfigured(res.encryption_configured);
  }, []);

  const refreshApprovals = useCallback(async () => {
    const res = await apiClient.listApprovals();
    setApprovals(res.approvals);
    setPendingApprovalCount(res.pending_count);
  }, []);

  const upsertApproval = useCallback((updated: Approval) => {
    setApprovals((prev) => {
      const next = prev.some((item) => item.id === updated.id)
        ? prev.map((item) => (item.id === updated.id ? updated : item))
        : [updated, ...prev];
      setPendingApprovalCount(next.filter((item) => item.status === "PENDING").length);
      return next;
    });
  }, []);

  const refreshAuth = useCallback(async () => {
    const [me, allUsers] = await Promise.all([apiClient.getMe(), apiClient.listUsers()]);
    setCurrentUser(me);
    setUsers(allUsers.users);
  }, []);

  const refreshHealth = useCallback(async () => {
    const res = await apiClient.getHealth();
    setHealth(res);
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      await Promise.all([
        refreshHealth(),
        refreshAuth(),
        refreshTasks(),
        refreshMemories(),
        refreshConversations(),
        refreshIntegrations(),
        refreshApprovals(),
      ]);
      setBackendError(null);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Unable to communicate with the LifeDesk AI backend.";
      setBackendError(msg);
    }
  }, [
    refreshApprovals,
    refreshAuth,
    refreshConversations,
    refreshHealth,
    refreshIntegrations,
    refreshMemories,
    refreshTasks,
  ]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  return {
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
    upsertApproval,
    refreshAuth,
    refreshHealth,
    refreshAll,
  };
}
