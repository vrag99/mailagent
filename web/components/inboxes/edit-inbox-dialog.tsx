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
import type { Inbox } from "@/lib/api-client";
import { toast } from "sonner";

interface EditInboxDialogProps {
  inbox: Inbox;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function EditInboxDialog({ inbox, open, onOpenChange, onUpdated }: EditInboxDialogProps) {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState(inbox.name || "");
  const [systemPrompt, setSystemPrompt] = useState(inbox.system_prompt || "");
  const [classifyProvider, setClassifyProvider] = useState(inbox.classify_provider);
  const [replyProvider, setReplyProvider] = useState(inbox.reply_provider);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await inboxes.update(inbox.address, {
        name: name || undefined,
        system_prompt: systemPrompt || undefined,
        classify_provider: classifyProvider,
        reply_provider: replyProvider,
      });
      toast.success("Inbox updated");
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update inbox");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit {inbox.address}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-name">Display Name</Label>
            <Input
              id="edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-classify">Classify Provider</Label>
            <Input
              id="edit-classify"
              value={classifyProvider}
              onChange={(e) => setClassifyProvider(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-reply">Reply Provider</Label>
            <Input
              id="edit-reply"
              value={replyProvider}
              onChange={(e) => setReplyProvider(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-prompt">System Prompt</Label>
            <Textarea
              id="edit-prompt"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
