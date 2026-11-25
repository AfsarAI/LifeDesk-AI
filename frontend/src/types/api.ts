export type NavPage = "chat" | "tasks" | "memory" | "settings";

export interface ToolExecutionRecord {
  call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  success: boolean;
  result: Record<string, unknown>;
}

export interface ChatResponse {
  conversation_id: number;
  reply: string;
  provider: string;
  model: string;
  iterations_used: number;
  tool_calls: ToolExecutionRecord[];
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  count: number;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant" | "tool" | string;
  content: string;
  tool_calls: ToolExecutionRecord[];
  created_at: string;
}

export interface MessageListResponse {
  conversation: Conversation;
  messages: ChatMessage[];
}

export interface Task {
  id: number;
  title: string;
  description: string | null;
  due_date: string | null;
  status: "pending" | "completed" | string;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  tasks: Task[];
  count: number;
  pending_count: number;
  completed_count: number;
}

export interface Memory {
  id: number;
  key: string;
  value: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  memories: Memory[];
  count: number;
}

export interface ProviderStatus {
  provider: string;
  model: string;
  base_url: string;
  configured: boolean;
  status_message: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  llm: ProviderStatus;
}
