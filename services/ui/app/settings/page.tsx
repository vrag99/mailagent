"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { health } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setApiUrl(localStorage.getItem("mailagent_api_url") || "/api");
      setApiKey(localStorage.getItem("mailagent_api_key") || "");
    }
  }, []);

  function handleSave() {
    localStorage.setItem("mailagent_api_url", apiUrl);
    localStorage.setItem("mailagent_api_key", apiKey);
    toast.success("Settings saved");
    checkConnection();
  }

  async function checkConnection() {
    setStatus("checking");
    try {
      await health.check();
      setStatus("ok");
    } catch {
      setStatus("error");
    }
  }

  useEffect(() => {
    checkConnection();
  }, []);

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">API Connection</CardTitle>
            <Badge
              variant={status === "ok" ? "default" : status === "error" ? "destructive" : "outline"}
            >
              {status === "ok" ? "Connected" : status === "error" ? "Disconnected" : "Checking..."}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="api-url">API URL</Label>
            <Input
              id="api-url"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="/api or http://localhost:8000"
            />
            <p className="text-xs text-muted-foreground">
              The base URL of your mailagent API. Use /api when behind nginx proxy.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="api-key">API Key</Label>
            <Input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="ma_..."
            />
            <p className="text-xs text-muted-foreground">
              Your mailagent API key. Create one with: mailagent api-key create
            </p>
          </div>

          <Separator />

          <div className="flex gap-2">
            <Button onClick={handleSave}>Save</Button>
            <Button variant="outline" onClick={checkConnection}>
              Test Connection
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
