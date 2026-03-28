"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { inboxes } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: inboxList } = useApi(() => inboxes.list());

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  function getSystemPrompt(): string {
    const inboxInfo = inboxList
      ?.map(
        (i) =>
          `- ${i.address}${i.name ? ` (${i.name})` : ""}: ${i.workflows.length} workflows [${i.workflows.map((w) => w.name).join(", ")}]`,
      )
      .join("\n");

    return `You are a helpful email assistant for mailagent. You help users manage their email inboxes and workflows.

Current inboxes:
${inboxInfo || "No inboxes configured yet."}

You can help users with:
- Understanding their email setup and workflows
- Suggesting workflow configurations
- Drafting email replies
- Explaining how mailagent processes emails
- Troubleshooting their configuration`;
  }

  async function handleSend() {
    if (!input.trim() || streaming) return;

    const userMessage: Message = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setStreaming(true);

    const apiKey = localStorage.getItem("chat_api_key") || "";
    const baseUrl = localStorage.getItem("chat_base_url") || "https://api.openai.com/v1";
    const model = localStorage.getItem("chat_model") || "gpt-4o";

    const apiMessages = [
      { role: "system" as const, content: getSystemPrompt() },
      ...newMessages,
    ];

    try {
      const res = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model,
          messages: apiMessages,
          stream: true,
        }),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(`API error: ${res.status} ${err}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let assistantContent = "";

      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter((line) => line.startsWith("data: "));

        for (const line of lines) {
          const data = line.slice(6);
          if (data === "[DONE]") break;

          try {
            const parsed = JSON.parse(data);
            const delta = parsed.choices?.[0]?.delta?.content;
            if (delta) {
              assistantContent += delta;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  content: assistantContent,
                };
                return updated;
              });
            }
          } catch {
            // skip unparseable chunks
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev.filter((m) => m.content !== ""),
        {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Failed to get response"}`,
        },
      ]);
    } finally {
      setStreaming(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-4 max-w-3xl mx-auto">
          {messages.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <p className="text-lg">Ask anything about your emails</p>
              <p className="text-sm mt-2">
                I have context about your inboxes and workflows.
              </p>
            </div>
          )}
          {messages.map((message, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                message.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <Card
                className={cn(
                  "px-4 py-3 max-w-[80%]",
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted",
                )}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              </Card>
            </div>
          ))}
          {streaming && messages[messages.length - 1]?.content === "" && (
            <div className="flex justify-start">
              <Card className="px-4 py-3 bg-muted">
                <p className="text-sm text-muted-foreground">Thinking...</p>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="border-t p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your emails... (Enter to send, Shift+Enter for new line)"
            rows={2}
            className="resize-none"
            disabled={streaming}
          />
          <Button onClick={handleSend} disabled={streaming || !input.trim()}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
