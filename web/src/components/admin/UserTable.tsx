"use client";

import { Fragment, useState } from "react";
import {
  pauseUser,
  resumeUser,
  revokeUser,
  type User,
} from "@/lib/adminApi";
import { dashboardUrl } from "@/lib/api";

interface UserTableProps {
  users: User[];
  onUpdate: (user: User) => void;
}

const STATUS_COLORS: Record<string, string> = {
  active: "text-green-400",
  paused: "text-yellow-400",
  revoked: "text-red-400",
  expired: "text-zinc-500",
};

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="rounded border border-[#2d3348] px-2 py-1 text-xs text-zinc-400 transition-colors hover:border-[#4c8dd6] hover:text-zinc-200"
    >
      {copied ? "Copied!" : label}
    </button>
  );
}

export default function UserTable({ users, onUpdate }: UserTableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  const filtered = users.filter((u) => {
    if (statusFilter && u.status !== statusFilter) return false;
    if (!search.trim()) return true;
    const hay = `${u.name ?? ""} ${u.email} ${u.plan_type} ${u.status}`.toLowerCase();
    return hay.includes(search.trim().toLowerCase());
  });

  const runAction = async (
    userId: string,
    action: "pause" | "resume" | "revoke",
  ) => {
    setActionError("");
    setActionLoading(`${action}-${userId}`);
    try {
      const fn =
        action === "pause"
          ? pauseUser
          : action === "resume"
            ? resumeUser
            : revokeUser;
      const updated = await fn(userId);
      onUpdate(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, email, plan…"
          className="min-w-[200px] flex-1 rounded-lg border border-[#2d3348] bg-[#0e1117] px-3 py-2 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-[#2d3348] bg-[#0e1117] px-3 py-2 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="revoked">Revoked</option>
          <option value="expired">Expired</option>
        </select>
      </div>

      {actionError && (
        <p className="text-sm text-red-400" role="alert">
          {actionError}
        </p>
      )}

      <p className="text-sm text-zinc-500">
        {filtered.length} of {users.length} subscribers
      </p>

      <div className="overflow-x-auto rounded-2xl border border-[#2d3348]">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-[#2d3348] bg-[#1a1d29] text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Days left</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#2d3348]">
            {filtered.map((u) => (
              <Fragment key={u.id}>
                <tr
                  key={u.id}
                  className="cursor-pointer bg-[#0e1117] transition-colors hover:bg-[#141820]"
                  onClick={() =>
                    setExpandedId(expandedId === u.id ? null : u.id)
                  }
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-zinc-100">
                      {u.name || "—"}
                    </div>
                    <div className="text-xs text-zinc-500">{u.email}</div>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">{u.plan_type}</td>
                  <td
                    className={`px-4 py-3 font-medium ${STATUS_COLORS[u.status] ?? "text-zinc-400"}`}
                  >
                    {u.status}
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    {u.days_remaining}
                  </td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex flex-wrap gap-1">
                      <button
                        type="button"
                        disabled={
                          u.status === "revoked" ||
                          actionLoading === `pause-${u.id}`
                        }
                        onClick={() => runAction(u.id, "pause")}
                        className="rounded border border-[#2d3348] px-2 py-1 text-xs text-zinc-300 hover:border-yellow-600 hover:text-yellow-400 disabled:opacity-40"
                      >
                        Pause
                      </button>
                      <button
                        type="button"
                        disabled={
                          u.status === "revoked" ||
                          actionLoading === `resume-${u.id}`
                        }
                        onClick={() => runAction(u.id, "resume")}
                        className="rounded border border-[#2d3348] px-2 py-1 text-xs text-zinc-300 hover:border-green-600 hover:text-green-400 disabled:opacity-40"
                      >
                        Resume
                      </button>
                      <button
                        type="button"
                        disabled={actionLoading === `revoke-${u.id}`}
                        onClick={() => runAction(u.id, "revoke")}
                        className="rounded border border-[#2d3348] px-2 py-1 text-xs text-zinc-300 hover:border-red-600 hover:text-red-400 disabled:opacity-40"
                      >
                        Revoke
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedId === u.id && (
                  <tr key={`${u.id}-detail`} className="bg-[#141820]">
                    <td colSpan={5} className="px-4 py-4">
                      <div className="grid gap-2 text-sm text-zinc-400 sm:grid-cols-2">
                        <div>
                          <span className="text-zinc-500">ID:</span> {u.id}
                        </div>
                        <div>
                          <span className="text-zinc-500">Created:</span>{" "}
                          {new Date(u.created_at).toLocaleString()}
                        </div>
                        <div>
                          <span className="text-zinc-500">Expires:</span>{" "}
                          {new Date(u.expires_at).toLocaleString()}
                        </div>
                        {u.stripe_customer_id && (
                          <div>
                            <span className="text-zinc-500">Stripe:</span>{" "}
                            {u.stripe_customer_id}
                          </div>
                        )}
                        <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
                          <span className="text-zinc-500">Access token:</span>
                          <code className="max-w-full truncate rounded bg-[#0e1117] px-2 py-1 text-xs text-zinc-300">
                            {u.access_token}
                          </code>
                          <CopyButton text={u.access_token} label="Copy token" />
                          <a
                            href={dashboardUrl(u.access_token)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded border border-[#2d3348] px-2 py-1 text-xs text-[#4c8dd6] hover:border-[#4c8dd6]"
                          >
                            Open dashboard
                          </a>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
                  No subscribers match your filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
