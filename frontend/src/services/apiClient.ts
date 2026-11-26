import type {
  ApprovalDecisionResponse,
  ApprovalListResponse,
  AuthSessionResponse,
  ChatResponse,
  ConversationListResponse,
  GoogleConnectResponse,
  GoogleDisconnectResponse,
  HealthResponse,
  IntegrationListResponse,
  Memory,
  MemoryListResponse,
  MessageListResponse,
  Task,
  TaskListResponse,
  UserProfile,
} from "../types/api";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000/api";

const SESSION_STORAGE_KEY = "lifedesk_session_token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getStoredSessionToken(): string | null {
  try {
    return window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredSessionToken(token: string | null): void {
  try {
    if (token) {
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {
    // Ignore storage unavailability in restricted contexts.
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const sessionToken = getStoredSessionToken();
  let response: Response;

  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Cannot reach the LifeDesk backend at http://127.0.0.1:8000. Make sure FastAPI is running.",
      0
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `Request failed with HTTP ${response.status}`;
    throw new ApiError(detail, response.status);
  }

  return body as T;
}

export const apiClient = {
  getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  getMe(): Promise<UserProfile> {
    return request<UserProfile>("/auth/me");
  },

  listUsers(): Promise<{ users: UserProfile[] }> {
    return request<{ users: UserProfile[] }>("/auth/users");
  },

  registerUser(payload: {
    name: string;
    email: string;
    timezone?: string;
  }): Promise<AuthSessionResponse> {
    return request<AuthSessionResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  loginUser(payload: { user_id?: number; email?: string }): Promise<AuthSessionResponse> {
    return request<AuthSessionResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateTimezone(timezone: string): Promise<UserProfile> {
    return request<UserProfile>("/auth/timezone", {
      method: "PATCH",
      body: JSON.stringify({ timezone }),
    });
  },

  sendChat(message: string, conversationId?: number | null): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId ?? null,
      }),
    });
  },

  listConversations(): Promise<ConversationListResponse> {
    return request<ConversationListResponse>("/conversations");
  },

  getConversationMessages(conversationId: number): Promise<MessageListResponse> {
    return request<MessageListResponse>(`/conversations/${conversationId}/messages`);
  },

  listTasks(params?: { status?: string; q?: string }): Promise<TaskListResponse> {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.q) search.set("q", params.q);
    const qs = search.toString();
    return request<TaskListResponse>(`/tasks${qs ? `?${qs}` : ""}`);
  },

  createTask(payload: {
    title: string;
    description?: string | null;
    due_date?: string | null;
  }): Promise<Task> {
    return request<Task>("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateTask(
    taskId: number,
    payload: {
      title?: string;
      description?: string | null;
      due_date?: string | null;
      status?: "pending" | "completed";
    }
  ): Promise<Task> {
    return request<Task>(`/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteTask(taskId: number): Promise<void> {
    return request<void>(`/tasks/${taskId}`, { method: "DELETE" });
  },

  listMemories(): Promise<MemoryListResponse> {
    return request<MemoryListResponse>("/memories");
  },

  createOrUpdateMemory(payload: { key: string; value: string }): Promise<Memory> {
    return request<Memory>("/memories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateMemory(memoryId: number, payload: { key?: string; value?: string }): Promise<Memory> {
    return request<Memory>(`/memories/${memoryId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteMemory(memoryId: number): Promise<void> {
    return request<void>(`/memories/${memoryId}`, { method: "DELETE" });
  },

  listIntegrations(): Promise<IntegrationListResponse> {
    return request<IntegrationListResponse>("/integrations");
  },

  connectGoogle(
    service: "gmail" | "calendar" | "both" = "both",
    accessLevel: "read" | "write" = "write"
  ): Promise<GoogleConnectResponse> {
    return request<GoogleConnectResponse>(
      `/integrations/google/connect?service=${service}&access_level=${accessLevel}`
    );
  },

  reconnectGoogle(
    service: "gmail" | "calendar" | "both" = "both",
    accessLevel: "read" | "write" = "write"
  ): Promise<GoogleConnectResponse> {
    return request<GoogleConnectResponse>(
      `/integrations/google/reconnect?service=${service}&access_level=${accessLevel}`,
      { method: "POST" }
    );
  },

  disconnectGoogle(
    provider: "gmail" | "calendar" | "both" = "both"
  ): Promise<GoogleDisconnectResponse> {
    return request<GoogleDisconnectResponse>(
      `/integrations/google/disconnect?provider=${provider}`,
      { method: "POST" }
    );
  },

  listApprovals(status?: string): Promise<ApprovalListResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<ApprovalListResponse>(`/approvals${qs}`);
  },

  approveAction(approvalId: number): Promise<ApprovalDecisionResponse> {
    return request<ApprovalDecisionResponse>(`/approvals/${approvalId}/approve`, {
      method: "POST",
    });
  },

  rejectAction(approvalId: number): Promise<ApprovalDecisionResponse> {
    return request<ApprovalDecisionResponse>(`/approvals/${approvalId}/reject`, {
      method: "POST",
    });
  },
};
