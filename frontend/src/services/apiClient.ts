import type {
  ChatResponse,
  ConversationListResponse,
  HealthResponse,
  Memory,
  MemoryListResponse,
  MessageListResponse,
  Task,
  TaskListResponse,
} from "../types/api";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000/api";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
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
    return request<void>(`/tasks/${taskId}`, {
      method: "DELETE",
    });
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
    return request<void>(`/memories/${memoryId}`, {
      method: "DELETE",
    });
  },
};
