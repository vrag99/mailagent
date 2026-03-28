"use client";

import { useState } from "react";
import { useApi } from "@/hooks/use-api";
import { providers } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { CreateProviderDialog } from "@/components/providers/create-provider-dialog";
import type { Provider } from "@/lib/types";
import { toast } from "sonner";

export default function ProvidersPage() {
  const { data: providerList, loading, error, refetch } = useApi(() => providers.list());
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await providers.delete(deleteTarget);
      toast.success("Provider deleted");
      setDeleteTarget(null);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete provider");
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading providers...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-destructive">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Providers</h1>
        <Button onClick={() => setCreateOpen(true)}>Add Provider</Button>
      </div>

      {providerList?.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No providers configured.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {providerList?.map((provider: Provider) => (
            <Card key={provider.name}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{provider.name}</CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => setDeleteTarget(provider.name)}
                  >
                    Delete
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex gap-2">
                  <Badge>{provider.type}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Model: {provider.model}
                </p>
                {provider.base_url && (
                  <p className="text-xs text-muted-foreground">
                    Base URL: {provider.base_url}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  Timeout: {provider.timeout}s | Retries: {provider.retries}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateProviderDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={refetch}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete provider?</AlertDialogTitle>
            <AlertDialogDescription>
              Delete provider &quot;{deleteTarget}&quot;? This will fail if any inbox is using it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
