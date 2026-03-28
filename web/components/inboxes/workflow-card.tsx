"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { workflows as workflowsApi } from "@/lib/api-client";
import type { Workflow } from "@/lib/types";
import { toast } from "sonner";

interface WorkflowCardProps {
  workflow: Workflow;
  inboxAddress: string;
  onDeleted: () => void;
}

export function WorkflowCard({ workflow, inboxAddress, onDeleted }: WorkflowCardProps) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await workflowsApi.delete(inboxAddress, workflow.name);
      toast.success(`Workflow "${workflow.name}" deleted`);
      setDeleteOpen(false);
      onDeleted();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete workflow");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">{workflow.name}</CardTitle>
            <div className="flex gap-2">
              <Badge>{workflow.action.type}</Badge>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs text-destructive"
                onClick={() => setDeleteOpen(true)}
              >
                Delete
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-1 text-xs text-muted-foreground">
          <p>
            <span className="font-medium">Intent:</span> {workflow.match.intent}
          </p>
          {workflow.match.keywords?.any && (
            <p>
              <span className="font-medium">Keywords (any):</span>{" "}
              {workflow.match.keywords.any.join(", ")}
            </p>
          )}
          {workflow.match.keywords?.all && (
            <p>
              <span className="font-medium">Keywords (all):</span>{" "}
              {workflow.match.keywords.all.join(", ")}
            </p>
          )}
          {workflow.action.prompt && (
            <p className="line-clamp-2">
              <span className="font-medium">Prompt:</span> {workflow.action.prompt}
            </p>
          )}
          {workflow.action.also_reply && <Badge variant="outline">+ reply</Badge>}
          {workflow.action.also_webhook && <Badge variant="outline">+ webhook</Badge>}
        </CardContent>
      </Card>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete workflow?</AlertDialogTitle>
            <AlertDialogDescription>
              Delete workflow &quot;{workflow.name}&quot; from {inboxAddress}?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
