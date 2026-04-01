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
import { providers } from "@/lib/api-client";
import { toast } from "sonner";

interface CreateProviderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

const PROVIDER_TYPES = ["groq", "openai", "anthropic", "gemini", "openrouter"];

export function CreateProviderDialog({ open, onOpenChange, onCreated }: CreateProviderDialogProps) {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("openai");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [timeout, setTimeout_] = useState("30");
  const [retries, setRetries] = useState("1");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await providers.create(name, {
        type,
        model,
        api_key: apiKey,
        base_url: baseUrl || undefined,
        timeout: parseInt(timeout) || 30,
        retries: parseInt(retries) || 1,
      });
      toast.success("Provider created");
      onOpenChange(false);
      onCreated();
      setName("");
      setModel("");
      setApiKey("");
      setBaseUrl("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create provider");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Provider</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="prov-name">Name</Label>
            <Input
              id="prov-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-openai"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="prov-type">Type</Label>
            <select
              id="prov-type"
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value)}
            >
              {PROVIDER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="prov-model">Model</Label>
            <Input
              id="prov-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="prov-key">API Key</Label>
            <Input
              id="prov-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="prov-url">Base URL (optional)</Label>
            <Input
              id="prov-url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="prov-timeout">Timeout (s)</Label>
              <Input
                id="prov-timeout"
                type="number"
                value={timeout}
                onChange={(e) => setTimeout_(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prov-retries">Retries</Label>
              <Input
                id="prov-retries"
                type="number"
                value={retries}
                onChange={(e) => setRetries(e.target.value)}
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
