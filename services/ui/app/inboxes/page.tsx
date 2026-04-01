"use client";

import { useState } from "react";
import Link from "next/link";
import { useApi } from "@/hooks/use-api";
import { inboxes } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CreateInboxDialog } from "@/components/inboxes/create-inbox-dialog";
import { DeleteInboxDialog } from "@/components/inboxes/delete-inbox-dialog";
import type { Inbox } from "@/lib/api-client";

export default function InboxesPage() {
  const { data: inboxList, loading, error, refetch } = useApi(() => inboxes.list());
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading inboxes...</p>
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
        <h1 className="text-2xl font-semibold">Inboxes</h1>
        <Button onClick={() => setCreateOpen(true)}>Create Inbox</Button>
      </div>

      {inboxList?.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No inboxes configured. Create one to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {inboxList?.map((inbox: Inbox) => (
            <Card key={inbox.address} className="group relative">
              <div className="absolute top-3 right-3 z-10" onClick={(e) => e.preventDefault()}>
                <DropdownMenu>
                  <DropdownMenuTrigger>
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                      ...
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => window.location.href = `/inboxes/${encodeURIComponent(inbox.address)}`}
                    >
                      View Details
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onClick={() => setDeleteTarget(inbox.address)}
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <Link href={`/inboxes/${encodeURIComponent(inbox.address)}`}>
                <CardHeader>
                  <CardTitle className="text-base">
                    {inbox.name || inbox.address}
                  </CardTitle>
                  {inbox.name && (
                    <p className="text-xs text-muted-foreground">{inbox.address}</p>
                  )}
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex gap-2 flex-wrap">
                    <Badge variant="outline">{inbox.classify_provider}</Badge>
                    <Badge variant="outline">{inbox.reply_provider}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {(inbox.workflows ?? []).length} workflow
                    {(inbox.workflows ?? []).length !== 1 ? "s" : ""}
                  </p>
                </CardContent>
              </Link>
            </Card>
          ))}
        </div>
      )}

      <CreateInboxDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={refetch}
      />

      {deleteTarget && (
        <DeleteInboxDialog
          address={deleteTarget}
          open={!!deleteTarget}
          onOpenChange={(open) => !open && setDeleteTarget(null)}
          onDeleted={refetch}
        />
      )}
    </div>
  );
}
