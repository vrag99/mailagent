import { client } from "./sdk/client.gen";
import {
  healthHealthGet,
  listInboxesApiInboxesGet,
  getInboxApiInboxesAddressGet,
  createInboxApiInboxesPost,
  updateInboxApiInboxesAddressPatch,
  deleteInboxApiInboxesAddressDelete,
  listWorkflowsApiInboxesInboxAddressWorkflowsGet,
  getWorkflowApiInboxesInboxAddressWorkflowsNameGet,
  createWorkflowApiInboxesInboxAddressWorkflowsPost,
  replaceWorkflowApiInboxesInboxAddressWorkflowsNamePut,
  deleteWorkflowApiInboxesInboxAddressWorkflowsNameDelete,
  listProvidersApiProvidersGet,
  getProviderApiProvidersNameGet,
  createProviderApiProvidersNamePost,
  updateProviderApiProvidersNamePut,
  deleteProviderApiProvidersNameDelete,
  sendApiEmailsSendPost,
} from "./sdk/sdk.gen";
import type {
  InboxRequest,
  InboxUpdateRequest,
  InboxResponse,
  WorkflowRequest,
  WorkflowResponse,
  ProviderRequest,
  ProviderResponse,
  SendEmailRequest,
  SendEmailResponse,
} from "./sdk/types.gen";

// Re-export types for components
export type {
  InboxResponse,
  InboxRequest,
  InboxUpdateRequest,
  WorkflowRequest,
  WorkflowResponse,
  ProviderRequest,
  ProviderResponse,
  SendEmailRequest,
  SendEmailResponse,
};

// Type alias for backwards compat
export type Inbox = InboxResponse;
export type Workflow = WorkflowResponse;
export type Provider = ProviderResponse;

export function configureClient() {
  const baseUrl =
    typeof window !== "undefined"
      ? localStorage.getItem("mailagent_api_url") || "/api"
      : process.env.NEXT_PUBLIC_API_URL || "/api";

  const apiKey =
    typeof window !== "undefined"
      ? localStorage.getItem("mailagent_api_key")
      : null;

  client.setConfig({ baseUrl });

  if (apiKey) {
    client.interceptors.request.use((request) => {
      request.headers.set("Authorization", `Bearer ${apiKey}`);
      return request;
    });
  }
}

// Configure on import
if (typeof window !== "undefined") {
  configureClient();
}

async function unwrap<T>(promise: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await promise;
  if (error) {
    const detail = (error as { detail?: string })?.detail || "Request failed";
    throw new Error(detail);
  }
  return data as T;
}

// Inboxes
export const inboxes = {
  list: () => unwrap<InboxResponse[]>(listInboxesApiInboxesGet()),
  get: (address: string) =>
    unwrap<InboxResponse>(getInboxApiInboxesAddressGet({ path: { address } })),
  create: (body: InboxRequest) =>
    unwrap<InboxResponse>(createInboxApiInboxesPost({ body })),
  update: (address: string, body: InboxUpdateRequest) =>
    unwrap<InboxResponse>(updateInboxApiInboxesAddressPatch({ path: { address }, body })),
  delete: (address: string) =>
    unwrap<void>(deleteInboxApiInboxesAddressDelete({ path: { address } })),
};

// Workflows
export const workflows = {
  list: (inboxAddress: string) =>
    unwrap<WorkflowResponse[]>(
      listWorkflowsApiInboxesInboxAddressWorkflowsGet({ path: { inbox_address: inboxAddress } }),
    ),
  get: (inboxAddress: string, name: string) =>
    unwrap<WorkflowResponse>(
      getWorkflowApiInboxesInboxAddressWorkflowsNameGet({
        path: { inbox_address: inboxAddress, name },
      }),
    ),
  create: (inboxAddress: string, body: WorkflowRequest) =>
    unwrap<WorkflowResponse>(
      createWorkflowApiInboxesInboxAddressWorkflowsPost({
        path: { inbox_address: inboxAddress },
        body,
      }),
    ),
  replace: (inboxAddress: string, name: string, body: WorkflowRequest) =>
    unwrap<WorkflowResponse>(
      replaceWorkflowApiInboxesInboxAddressWorkflowsNamePut({
        path: { inbox_address: inboxAddress, name },
        body,
      }),
    ),
  delete: (inboxAddress: string, name: string) =>
    unwrap<void>(
      deleteWorkflowApiInboxesInboxAddressWorkflowsNameDelete({
        path: { inbox_address: inboxAddress, name },
      }),
    ),
};

// Providers
export const providers = {
  list: () => unwrap<ProviderResponse[]>(listProvidersApiProvidersGet()),
  get: (name: string) =>
    unwrap<ProviderResponse>(getProviderApiProvidersNameGet({ path: { name } })),
  create: (name: string, body: ProviderRequest) =>
    unwrap<ProviderResponse>(createProviderApiProvidersNamePost({ path: { name }, body })),
  update: (name: string, body: ProviderRequest) =>
    unwrap<ProviderResponse>(updateProviderApiProvidersNamePut({ path: { name }, body })),
  delete: (name: string) =>
    unwrap<void>(deleteProviderApiProvidersNameDelete({ path: { name } })),
};

// Emails
export const emails = {
  send: (body: SendEmailRequest) =>
    unwrap<SendEmailResponse>(sendApiEmailsSendPost({ body })),
};

// Health
export const health = {
  check: () => unwrap<{ [key: string]: unknown }>(healthHealthGet()) as Promise<{ status: string }>,
};
