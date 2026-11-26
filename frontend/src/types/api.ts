export type NavPage = "chat" | "tasks" | "memory" | "integrations" | "settings";

export interface UserProfile {
  id: number;
  name: string | null;
  email: string | null;
  timezone: string;
  created_at: string;
}

export interface AuthSessionResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface ToolExecutionRecord {
  call_id: string;
  tool_name: string;
  tool_source?: string;
  arguments: Record<string, unknown>;
  success: boolean;
  result: Record<string, unknown>;
  approval_id?: number | null;
}

export interface Approval {
  id: number;
  user_id: number;
  conversation_id: number | null;
  provider: string;
  tool_name: string;
  action_type: string;
  action_payload: Record<string, unknown>;
  summary: string;
  status: "PENDING" | "APPROVED" | "EXECUTED" | "REJECTED" | "EXPIRED" | "FAILED" | "CANCELLED" | string;
  expires_at: string;
  created_at: string;
  approved_at: string | null;
  executed_at: string | null;
  execution_result: Record<string, unknown> | null;
}

export interface ApprovalListResponse {
  approvals: Approval[];
  pending_count: number;
}

export interface ApprovalDecisionResponse {
  approval: Approval;
  message: string;
}

export interface ChatResponse {
  conversation_id: number;
  reply: string;
  provider: string;
  model: string;
  iterations_used: number;
  tool_calls: ToolExecutionRecord[];
  pending_approvals: Approval[];
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

export interface IntegrationCard {
  provider: string;
  display_name: string;
  description: string;
  category: "active" | "coming_soon" | string;
  status: "connected" | "disconnected" | "needs_reconnect" | "coming_soon" | string;
  account_email: string | null;
  granted_scopes: string[];
  available_permissions: string[];
  last_connected_at: string | null;
  oauth_configured: boolean;
  demo_mode_active: boolean;
}

export interface IntegrationListResponse {
  integrations: IntegrationCard[];
  oauth_configured: boolean;
  encryption_configured: boolean;
}

export interface GoogleConnectResponse {
  authorization_url: string;
  state: string;
  service: string;
  requested_scopes: string[];
}

export interface GoogleDisconnectResponse {
  disconnected: string[];
  message: string;
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
