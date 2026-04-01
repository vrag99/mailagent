"use client";

import { useState, useEffect } from "react";
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
import { toast } from "sonner";

interface ChatSettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const PROVIDERS = [
  { value: "openai", label: "OpenAI", baseUrl: "https://api.openai.com/v1" },
  { value: "anthropic", label: "Anthropic", baseUrl: "https://api.anthropic.com" },
  { value: "groq", label: "Groq", baseUrl: "https://api.groq.com/openai/v1" },
  { value: "openrouter", label: "OpenRouter", baseUrl: "https://openrouter.ai/api/v1" },
  { value: "custom", label: "Custom (OpenAI-compatible)", baseUrl: "" },
];

export function ChatSettings({ open, onOpenChange }: ChatSettingsProps) {
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [model, setModel] = useState("gpt-4o");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setApiKey(localStorage.getItem("chat_api_key") || "");
      setBaseUrl(localStorage.getItem("chat_base_url") || "https://api.openai.com/v1");
      setModel(localStorage.getItem("chat_model") || "gpt-4o");
      setProvider(localStorage.getItem("chat_provider") || "openai");
    }
  }, [open]);

  function handleProviderChange(value: string) {
    setProvider(value);
    const p = PROVIDERS.find((p) => p.value === value);
    if (p && p.baseUrl) {
      setBaseUrl(p.baseUrl);
    }
  }

  function handleSave() {
    localStorage.setItem("chat_api_key", apiKey);
    localStorage.setItem("chat_base_url", baseUrl);
    localStorage.setItem("chat_model", model);
    localStorage.setItem("chat_provider", provider);
    toast.success("Chat settings saved");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Chat Settings (BYOK)</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Provider</Label>
            <select
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="chat-key">API Key</Label>
            <Input
              id="chat-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
            />
            <p className="text-xs text-muted-foreground">
              Stored locally in your browser. Never sent to our servers.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="chat-model">Model</Label>
            <Input
              id="chat-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o"
            />
          </div>
          {provider === "custom" && (
            <div className="space-y-2">
              <Label htmlFor="chat-url">Base URL</Label>
              <Input
                id="chat-url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
