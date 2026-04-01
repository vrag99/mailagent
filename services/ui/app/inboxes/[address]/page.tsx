"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useApi } from "@/hooks/use-api";
import { inboxes } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkflowCard } from "@/components/inboxes/workflow-card";
import { EditInboxDialog } from "@/components/inboxes/edit-inbox-dialog";
import { DeleteInboxDialog } from "@/components/inboxes/delete-inbox-dialog";
import { CreateWorkflowDialog } from "@/components/inboxes/create-workflow-dialog";
import { ComposeEmail } from "@/components/emails/compose-email";

export default function InboxDetailPage() {
  const params = useParams();
  const router = useRouter();
  const address = decodeURIComponent(params.address as string);

  const { data: inbox, loading, error, refetch } = useApi(
    () => inboxes.get(address),
    [address],
  );

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [createWfOpen, setCreateWfOpen] = useState(false);

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading inbox...</p>
      </div>
    );
  }

  if (error || !inbox) {
    return (
      <div className="p-6">
        <p className="text-destructive">Error: {error || "Inbox not found"}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{inbox.name || inbox.address}</h1>
          {inbox.name && (
            <p className="text-sm text-muted-foreground">{inbox.address}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            Edit
          </Button>
          <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
            Delete
          </Button>
        </div>
      </div>

      <div className="flex gap-2">
        <Badge variant="outline">Classify: {inbox.classify_provider}</Badge>
        <Badge variant="outline">Reply: {inbox.reply_provider}</Badge>
      </div>

      {inbox.system_prompt && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">System Prompt</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {inbox.system_prompt}
            </p>
          </CardContent>
        </Card>
      )}

      <Separator />

      <Tabs defaultValue="workflows">
        <TabsList>
          <TabsTrigger value="workflows">Workflows</TabsTrigger>
          <TabsTrigger value="compose">Compose</TabsTrigger>
        </TabsList>

        <TabsContent value="workflows" className="space-y-4 mt-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">
              Workflows ({(inbox.workflows ?? []).length})
            </h2>
            <Button size="sm" onClick={() => setCreateWfOpen(true)}>
              Add Workflow
            </Button>
          </div>
          <div className="grid gap-3">
            {(inbox.workflows ?? []).map((wf) => (
              <WorkflowCard
                key={wf.name}
                workflow={wf}
                inboxAddress={inbox.address}
                onDeleted={refetch}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="compose" className="mt-4">
          <ComposeEmail fromInbox={inbox.address} />
        </TabsContent>
      </Tabs>

      <EditInboxDialog
        inbox={inbox}
        open={editOpen}
        onOpenChange={setEditOpen}
        onUpdated={refetch}
      />
      <DeleteInboxDialog
        address={inbox.address}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => router.push("/inboxes")}
      />
      <CreateWorkflowDialog
        inboxAddress={inbox.address}
        open={createWfOpen}
        onOpenChange={setCreateWfOpen}
        onCreated={refetch}
      />
    </div>
  );
}
