"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { emails } from "@/lib/api-client";
import { toast } from "sonner";

interface ComposeEmailProps {
  fromInbox: string;
  replyTo?: {
    to: string;
    subject: string;
    messageId?: string;
    references?: string;
  };
}

export function ComposeEmail({ fromInbox, replyTo }: ComposeEmailProps) {
  const [to, setTo] = useState(replyTo?.to || "");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState(
    replyTo ? `Re: ${replyTo.subject.replace(/^Re:\s*/i, "")}` : "",
  );
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    try {
      const result = await emails.send({
        from_inbox: fromInbox,
        to: to.split(",").map((s) => s.trim()),
        cc: cc ? cc.split(",").map((s) => s.trim()) : [],
        subject,
        body,
        content_type: "plain",
        in_reply_to: replyTo?.messageId || undefined,
        references: replyTo?.references || undefined,
      });
      if (result.ok) {
        toast.success("Email sent");
        setTo(replyTo?.to || "");
        setSubject(replyTo ? `Re: ${replyTo.subject.replace(/^Re:\s*/i, "")}` : "");
        setBody("");
        setCc("");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send email");
    } finally {
      setSending(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          {replyTo ? "Reply" : "Compose Email"}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSend} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="to">To</Label>
            <Input
              id="to"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="recipient@example.com"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cc">CC (optional)</Label>
            <Input
              id="cc"
              value={cc}
              onChange={(e) => setCc(e.target.value)}
              placeholder="cc@example.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="subject">Subject</Label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Subject"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="body">Body</Label>
            <Textarea
              id="body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write your email..."
              rows={8}
              required
            />
          </div>
          <div className="flex justify-end">
            <Button type="submit" disabled={sending}>
              {sending ? "Sending..." : "Send"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
