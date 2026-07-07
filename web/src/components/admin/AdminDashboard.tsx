"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE_URL, DASHBOARD_URL, apiUrl } from "@/lib/api";
import {
  AdminApiError,
  fetchAdminStats,
  fetchUsers,
  type AdminStats,
  type User,
} from "@/lib/adminApi";
import { clearAdminKey } from "@/lib/adminAuth";
import CreateUserForm from "./CreateUserForm";
import UserTable from "./UserTable";

type BackendStatus = "checking" | "online" | "offline";

export default function AdminDashboard() {
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const checkBackend = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/healthcheck"), {
        cache: "no-store",
      });
      setBackendStatus(res.ok ? "online" : "offline");
    } catch {
      setBackendStatus("offline");
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [userList, adminStats] = await Promise.all([
        fetchUsers(),
        fetchAdminStats(),
      ]);
      setUsers(userList);
      setStats(adminStats);
    } catch (err) {
      if (err instanceof AdminApiError && err.status === 401) {
        clearAdminKey();
        window.location.reload();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load admin data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkBackend();
    loadData();
    const interval = setInterval(checkBackend, 15_000);
    return () => clearInterval(interval);
  }, [checkBackend, loadData]);

  const handleUserUpdate = (updated: User) => {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    loadData();
  };

  const handleUserCreated = (user: User) => {
    setUsers((prev) => [user, ...prev]);
    loadData();
  };

  const statusEmoji = {
    checking: "⚪",
    online: "🟢",
    offline: "🔴",
  }[backendStatus];

  const statusLabel = {
    checking: "Checking…",
    online: "Connected",
    offline: "Offline",
  }[backendStatus];

  return (
    <div className="flex w-full max-w-6xl flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-zinc-50">
            Admin Control Tower
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Manage subscribers and licenses
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="rounded-full border border-[#2d3348] px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-[#1a1d29] disabled:opacity-50"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => {
              clearAdminKey();
              window.location.reload();
            }}
            className="rounded-full border border-[#2d3348] px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-[#1a1d29]"
          >
            Log out
          </button>
          <Link
            href="/"
            className="rounded-full border border-[#2d3348] px-4 py-2 text-sm text-zinc-300 transition-colors hover:bg-[#1a1d29]"
          >
            Marketing site
          </Link>
          <a
            href={DASHBOARD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full bg-[#4c8dd6] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3a7bc0]"
          >
            Main dashboard
          </a>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span
          role="status"
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm ${
            backendStatus === "online"
              ? "border-green-800 bg-green-950 text-green-300"
              : backendStatus === "offline"
                ? "border-red-800 bg-red-950 text-red-300"
                : "border-zinc-700 bg-zinc-800 text-zinc-300"
          }`}
        >
          {statusEmoji} Backend: {statusLabel}
        </span>
        <span className="text-xs text-zinc-500">{API_BASE_URL}</span>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "Total users", value: stats.total_users },
            { label: "Active", value: stats.total_active },
            { label: "Pending renewals", value: stats.pending_renewals },
            { label: "Paused", value: stats.paused },
            { label: "Individual", value: stats.active_individual },
            { label: "Enterprise", value: stats.active_enterprise },
          ].map((m) => (
            <div
              key={m.label}
              className="rounded-xl border border-[#2d3348] bg-[#1a1d29] p-4"
            >
              <div className="text-2xl font-bold text-zinc-50">{m.value}</div>
              <div className="text-xs text-zinc-500">{m.label}</div>
            </div>
          ))}
        </div>
      )}

      <CreateUserForm onCreated={handleUserCreated} />

      {error && (
        <p className="rounded-lg border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-center text-zinc-500">Loading subscribers…</p>
      ) : (
        <UserTable users={users} onUpdate={handleUserUpdate} />
      )}
    </div>
  );
}
