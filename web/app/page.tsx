"use client";

import { useApi } from "@/hooks/use-api";
import { inboxes, providers, health } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

export default function DashboardPage() {
  const { data: inboxList, loading: inboxLoading } = useApi(() => inboxes.list());
  const { data: providerList, loading: providerLoading } = useApi(() => providers.list());
  const { data: healthStatus } = useApi(() => health.check());

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <Badge variant={healthStatus?.status === "ok" ? "default" : "destructive"}>
          {healthStatus?.status === "ok" ? "Connected" : "Disconnected"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Link href="/inboxes">
          <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Inboxes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {inboxLoading ? "..." : inboxList?.length ?? 0}
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link href="/providers">
          <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Providers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {providerLoading ? "..." : providerList?.length ?? 0}
              </div>
            </CardContent>
          </Card>
        </Link>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Workflows
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {inboxLoading
                ? "..."
                : inboxList?.reduce((sum, i) => sum + (i.workflows ?? []).length, 0) ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {inboxList && inboxList.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-medium">Recent Inboxes</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {inboxList.slice(0, 4).map((inbox) => (
              <Link key={inbox.address} href={`/inboxes/${encodeURIComponent(inbox.address)}`}>
                <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">{inbox.name || inbox.address}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-muted-foreground">{inbox.address}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {(inbox.workflows ?? []).length} workflow{(inbox.workflows ?? []).length !== 1 ? "s" : ""}
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
