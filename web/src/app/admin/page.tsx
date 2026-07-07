"use client";

import { useEffect, useState } from "react";
import AdminDashboard from "@/components/admin/AdminDashboard";
import AdminLogin from "@/components/admin/AdminLogin";
import { getAdminKey } from "@/lib/adminAuth";

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setAuthed(!!getAdminKey());
    setReady(true);
  }, []);

  if (!ready) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[#0e1117] text-zinc-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-[#0e1117] px-6 py-12">
      {authed ? (
        <AdminDashboard />
      ) : (
        <AdminLogin onSuccess={() => setAuthed(true)} />
      )}
    </div>
  );
}
