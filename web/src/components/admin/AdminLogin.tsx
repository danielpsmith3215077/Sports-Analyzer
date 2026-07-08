"use client";

import { useState } from "react";
import { verifyAdminKey } from "@/lib/adminApi";
import { setAdminKey } from "@/lib/adminAuth";

interface AdminLoginProps {
  onSuccess: () => void;
}

export default function AdminLogin({ onSuccess }: AdminLoginProps) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!key.trim()) {
      setError("Enter your admin API key.");
      return;
    }
    setLoading(true);
    try {
      const result = await verifyAdminKey(key.trim());
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setAdminKey(key.trim());
      onSuccess();
    } catch {
      setError("Could not reach the backend API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex w-full max-w-md flex-col gap-6 rounded-2xl border border-[#2d3348] bg-[#1a1d29] p-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-zinc-50">Admin Login</h1>
        <p className="mt-2 text-sm text-zinc-400">
          Enter the admin API key to manage subscribers.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Admin API key"
          autoComplete="current-password"
          className="rounded-lg border border-[#2d3348] bg-[#0e1117] px-4 py-3 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        />
        {error && (
          <p className="text-sm text-red-400" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-[#4c8dd6] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#3a7bc0] disabled:opacity-50"
        >
          {loading ? "Verifying…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
