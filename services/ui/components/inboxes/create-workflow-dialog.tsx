"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { workflows } from "@/lib/api-client";
import { toast } from "sonner";

interface CreateWorkflowDialogProps {
  inboxAddress: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateWorkflowDialog({
  inboxAddress,
  open,
  onOpenChange,
  onCreated,
}: CreateWorkflowDialogProps) {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [intent, setIntent] = useState("");
  const [actionType, setActionType] = useState("reply");
  const [prompt, setPrompt] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [keywordsAny, setKeywordsAny] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await workflows.create(inboxAddress, {
        name,
        match: {
          intent,
          keywords: keywordsAny
            ? { any: keywordsAny.split(",").map((k) => k.trim()) }
            : undefined,
        },
        action: {
          type: actionType,
          prompt: prompt || undefined,
          webhook: webhookUrl || undefined,
        },
      });
      toast.success("Workflow created");
      onOpenChange(false);
      onCreated();
      setName("");
      setIntent("");
      setPrompt("");
      setWebhookUrl("");
      setKeywordsAny("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create workflow");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Workflow</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wf-name">Name</Label>
            <Input
              id="wf-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="support-reply"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wf-intent">Intent</Label>
            <Input
              id="wf-intent"
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder="Customer asking for help or support"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wf-keywords">Keywords (comma-separated, optional)</Label>
            <Input
              id="wf-keywords"
              value={keywordsAny}
              onChange={(e) => setKeywordsAny(e.target.value)}
              placeholder="help, support, issue"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="wf-action-type">Action Type</Label>
            <select
              id="wf-action-type"
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
            >
              <option value="reply">Reply</option>
              <option value="ignore">Ignore</option>
              <option value="notify">Notify</option>
              <option value="webhook">Webhook</option>
            </select>
          </div>
          {(actionType === "reply" || actionType === "notify") && (
            <div className="space-y-2">
              <Label htmlFor="wf-prompt">Reply Prompt</Label>
              <Textarea
                id="wf-prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Reply politely and offer to help..."
                rows={3}
              />
            </div>
          )}
          {(actionType === "webhook" || actionType === "notify") && (
            <div className="space-y-2">
              <Label htmlFor="wf-webhook">Webhook URL</Label>
              <Input
                id="wf-webhook"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://hooks.example.com/notify"
              />
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
