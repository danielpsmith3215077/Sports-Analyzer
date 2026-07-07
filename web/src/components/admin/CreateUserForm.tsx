"use client";

import { useState } from "react";
import { createUser, type User } from "@/lib/adminApi";

interface CreateUserFormProps {
  onCreated: (user: User) => void;
}

export default function CreateUserForm({ onCreated }: CreateUserFormProps) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [planType, setPlanType] = useState("individual");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !name.trim()) {
      setError("Email and name are required.");
      return;
    }
    setLoading(true);
    try {
      const user = await createUser({
        email: email.trim(),
        name: name.trim(),
        plan_type: planType,
      });
      setEmail("");
      setName("");
      setPlanType("individual");
      onCreated(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-2xl border border-[#2d3348] bg-[#1a1d29] p-6"
    >
      <h3 className="text-lg font-semibold text-zinc-50">Create user manually</h3>
      <p className="text-sm text-zinc-400">
        Owner bypass — provisions a license without Stripe checkout.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          className="rounded-lg border border-[#2d3348] bg-[#0e1117] px-3 py-2 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        />
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name"
          className="rounded-lg border border-[#2d3348] bg-[#0e1117] px-3 py-2 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        />
        <select
          value={planType}
          onChange={(e) => setPlanType(e.target.value)}
          className="rounded-lg border border-[#2d3348] bg-[#0e1117] px-3 py-2 text-sm text-zinc-50 outline-none focus:border-[#4c8dd6]"
        >
          <option value="individual">Individual</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>
      {error && (
        <p className="text-sm text-red-400" role="alert">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={loading}
        className="self-start rounded-full bg-[#4c8dd6] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3a7bc0] disabled:opacity-50"
      >
        {loading ? "Creating…" : "Create user"}
      </button>
    </form>
  );
}
