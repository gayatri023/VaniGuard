"use client";
import { useState } from "react";
import Dashboard from "@/components/admin/Dashboard";
import { Button, Card, Heading } from "@/components/ui";
import { readStored, writeStored } from "@/lib/store";

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(() => (typeof window === "undefined" ? null : readStored("vg_admin")));
  const [draft, setDraft] = useState("");
  if (token) {
    return <Dashboard token={token} onSignOut={() => { writeStored("vg_admin", null); setToken(null); }} />;
  }
  return (
    <div className="mx-auto max-w-md p-4 pt-16">
      <Card tone="high" className="space-y-5">
        <Heading icon="lock" sub="Read-only dashboard. The token is kept in this tab only and is never put in a URL.">Admin sign-in</Heading>
        <label htmlFor="token" className="type-title-m block">Admin token</label>
        <input id="token" type="password" autoComplete="off" value={draft} onChange={(e) => setDraft(e.target.value)}
          className="min-h-14 w-full rounded-2xl border border-outline bg-surface px-4 text-on-surface" />
        <Button disabled={draft.length < 8} onClick={() => { writeStored("vg_admin", draft); setToken(draft); }}>Open dashboard</Button>
      </Card>
    </div>
  );
}
