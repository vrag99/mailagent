// Types mirroring the FastAPI Pydantic models

export interface Provider {
  name: string;
  type: string;
  model: string;
  base_url?: string | null;
  timeout: number;
  retries: number;
}

export interface ProviderRequest {
  type: string;
  model: string;
  api_key: string;
  base_url?: string | null;
  timeout?: number;
  retries?: number;
  http_referer?: string | null;
  x_title?: string | null;
}

export interface KeywordMatch {
  any?: string[] | null;
  all?: string[] | null;
}

export interface WorkflowMatch {
  intent: string;
  keywords?: KeywordMatch | null;
}

export interface WorkflowAction {
  type: string;
  prompt?: string | null;
  webhook?: string | null;
  url?: string | null;
  method?: string;
  headers?: Record<string, string> | null;
  payload?: Record<string, unknown> | null;
  also_reply?: boolean;
  also_webhook?: boolean;
  webhook_url?: string | null;
}

export interface Workflow {
  name: string;
  match: WorkflowMatch;
  action: WorkflowAction;
}

export interface WorkflowRequest {
  name: string;
  match: WorkflowMatch;
  action: WorkflowAction;
}

export interface Inbox {
  address: string;
  name?: string | null;
  classify_provider: string;
  reply_provider: string;
  system_prompt?: string | null;
  workflows: Workflow[];
}

export interface InboxCreateRequest {
  address: string;
  password: string;
  name?: string | null;
  classify_provider?: string | null;
  reply_provider?: string | null;
  system_prompt?: string | null;
  blocklist?: Blocklist | null;
  workflows: WorkflowRequest[];
}

export interface InboxUpdateRequest {
  name?: string | null;
  classify_provider?: string | null;
  reply_provider?: string | null;
  system_prompt?: string | null;
  blocklist?: Blocklist | null;
}

export interface Blocklist {
  from_patterns: string[];
  headers: string[];
}

export interface SendEmailRequest {
  from_inbox: string;
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  body: string;
  content_type?: "plain" | "html";
  in_reply_to?: string | null;
  references?: string | null;
}

export interface SendEmailResponse {
  ok: boolean;
  message_id?: string | null;
  detail?: string | null;
}

export interface ErrorResponse {
  detail: string;
}
