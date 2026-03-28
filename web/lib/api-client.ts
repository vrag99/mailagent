import type {
  Inbox,
  InboxCreateRequest,
  InboxUpdateRequest,
  Provider,
  ProviderRequest,
  SendEmailRequest,
  SendEmailResponse,
  Workflow,
  WorkflowRequest,
} from "./types";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

function getBaseUrl(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("mailagent_api_url") || "/api";
  }
  return process.env.NEXT_PUBLIC_API_URL || "/api";
}

function getApiKey(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("mailagent_api_key");
  }
  return null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const baseUrl = getBaseUrl();
  const apiKey = getApiKey();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const res = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

// Inboxes
export const inboxes = {
  list: () => request<Inbox[]>("/inboxes"),
  get: (address: string) => request<Inbox>(`/inboxes/${encodeURIComponent(address)}`),
  create: (data: InboxCreateRequest) =>
    request<Inbox>("/inboxes", { method: "POST", body: JSON.stringify(data) }),
  update: (address: string, data: InboxUpdateRequest) =>
    request<Inbox>(`/inboxes/${encodeURIComponent(address)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  delete: (address: string) =>
    request<void>(`/inboxes/${encodeURIComponent(address)}`, { method: "DELETE" }),
};

// Workflows
export const workflows = {
  list: (inboxAddress: string) =>
    request<Workflow[]>(
      `/inboxes/${encodeURIComponent(inboxAddress)}/workflows`,
    ),
  get: (inboxAddress: string, name: string) =>
    request<Workflow>(
      `/inboxes/${encodeURIComponent(inboxAddress)}/workflows/${encodeURIComponent(name)}`,
    ),
  create: (inboxAddress: string, data: WorkflowRequest) =>
    request<Workflow>(
      `/inboxes/${encodeURIComponent(inboxAddress)}/workflows`,
      { method: "POST", body: JSON.stringify(data) },
    ),
  replace: (inboxAddress: string, name: string, data: WorkflowRequest) =>
    request<Workflow>(
      `/inboxes/${encodeURIComponent(inboxAddress)}/workflows/${encodeURIComponent(name)}`,
      { method: "PUT", body: JSON.stringify(data) },
    ),
  delete: (inboxAddress: string, name: string) =>
    request<void>(
      `/inboxes/${encodeURIComponent(inboxAddress)}/workflows/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),
};

// Providers
export const providers = {
  list: () => request<Provider[]>("/providers"),
  get: (name: string) => request<Provider>(`/providers/${encodeURIComponent(name)}`),
  create: (name: string, data: ProviderRequest) =>
    request<Provider>(`/providers/${encodeURIComponent(name)}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (name: string, data: ProviderRequest) =>
    request<Provider>(`/providers/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (name: string) =>
    request<void>(`/providers/${encodeURIComponent(name)}`, { method: "DELETE" }),
};

// Emails
export const emails = {
  send: (data: SendEmailRequest) =>
    request<SendEmailResponse>("/emails/send", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// Health
export const health = {
  check: () => request<{ status: string }>("/health"),
};

export { ApiError };
