"use client";

import { useState } from "react";
import { ChatInterface } from "@/components/chat/chat-interface";
import { ChatSettings } from "@/components/chat/chat-settings";
import { Button } from "@/components/ui/button";

export default function ChatPage() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Check if LLM settings are configured
  const hasApiKey = typeof window !== "undefined" && !!localStorage.getItem("chat_api_key");

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)]">
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h1 className="text-lg font-semibold">Chat</h1>
          <p className="text-xs text-muted-foreground">
            Talk about your emails with AI
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setSettingsOpen(true)}>
          Settings
        </Button>
      </div>

      {!hasApiKey ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <p className="text-muted-foreground">
              Configure your LLM API key to start chatting.
            </p>
            <Button onClick={() => setSettingsOpen(true)}>Configure API Key</Button>
          </div>
        </div>
      ) : (
        <ChatInterface />
      )}

      <ChatSettings open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  );
}
