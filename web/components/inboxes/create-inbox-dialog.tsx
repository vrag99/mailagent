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
import { inboxes } from "@/lib/api-client";
import { toast } from "sonner";

interface CreateInboxDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateInboxDialog({ open, onOpenChange, onCreated }: CreateInboxDialogProps) {
  const [loading, setLoading] = useState(false);
  const [address, setAddress] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [workflowName, setWorkflowName] = useState("fallback");
  const [workflowIntent, setWorkflowIntent] = useState("Catch-all for unclassified emails");
  const [workflowAction, setWorkflowAction] = useState("ignore");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await inboxes.create({
        address,
        password,
        name: name || undefined,
        system_prompt: systemPrompt || undefined,
        workflows: [
          {
            name: workflowName,
            match: { intent: workflowIntent },
            action: { type: workflowAction },
          },
        ],
      });
      toast.success("Inbox created");
      onOpenChange(false);
      onCreated();
      setAddress("");
      setPassword("");
      setName("");
      setSystemPrompt("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create inbox");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Inbox</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="address">Email Address</Label>
            <Input
              id="address"
              type="email"
              placeholder="user@example.com"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Display Name (optional)</Label>
            <Input
              id="name"
              placeholder="My Inbox"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="system-prompt">System Prompt (optional)</Label>
            <Textarea
              id="system-prompt"
              placeholder="You are an email assistant..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={3}
            />
          </div>
          <div className="border rounded-lg p-3 space-y-3">
            <p className="text-sm font-medium">Default Workflow</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="wf-name">Name</Label>
                <Input
                  id="wf-name"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="wf-action">Action</Label>
                <select
                  id="wf-action"
                  className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
                  value={workflowAction}
                  onChange={(e) => setWorkflowAction(e.target.value)}
                >
                  <option value="ignore">Ignore</option>
                  <option value="reply">Reply</option>
                  <option value="notify">Notify</option>
                  <option value="webhook">Webhook</option>
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="wf-intent">Intent</Label>
              <Input
                id="wf-intent"
                value={workflowIntent}
                onChange={(e) => setWorkflowIntent(e.target.value)}
                required
              />
            </div>
          </div>
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
