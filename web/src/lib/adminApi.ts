import { apiUrl } from "@/lib/api";
import { getAdminKey } from "@/lib/adminAuth";

export interface User {
  id: string;
  email: string;
  name: string | null;
  plan_type: string;
  access_token: string;
  stripe_customer_id: string | null;
  parent_enterprise_id: string | null;
  created_at: string;
  expires_at: string;
  status: string;
  days_remaining: number;
}

export interface AdminStats {
  total_users: number;
  total_active: number;
  pending_renewals: number;
  paused: number;
  revoked: number;
  active_individual: number;
  active_enterprise: number;
}

export class AdminApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "AdminApiError";
  }
}

function adminHeaders(key?: string): HeadersInit {
  const adminKey = key ?? getAdminKey();
  if (!adminKey) {
    throw new AdminApiError(401, "Not signed in");
  }
  return {
    "Content-Type": "application/json",
    "X-Admin-Key": adminKey,
  };
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function verifyAdminKey(key: string): Promise<boolean> {
  const res = await fetch(apiUrl("/admin/verify"), {
    method: "POST",
    headers: adminHeaders(key),
  });
  return res.ok;
}

export async function fetchAdminStats(): Promise<AdminStats> {
  const res = await fetch(apiUrl("/admin/stats"), {
    headers: adminHeaders(),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  return res.json();
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch(apiUrl("/users"), {
    headers: adminHeaders(),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  return res.json();
}

export async function createUser(payload: {
  email: string;
  name: string;
  plan_type: string;
}): Promise<User> {
  const res = await fetch(apiUrl("/users"), {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  return res.json();
}

export async function pauseUser(userId: string): Promise<User> {
  const res = await fetch(apiUrl(`/users/${userId}/pause`), {
    method: "POST",
    headers: adminHeaders(),
  });
  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  return res.json();
}

export async function resumeUser(userId: string): Promise<User> {
  const res = await fetch(apiUrl(`/users/${userId}/resume`), {
    method: "POST",
    headers: adminHeaders(),
  });
  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  return res.json();
}

export async function revokeUser(userId: string): Promise<User> {
  const res = await fetch(apiUrl(`/users/${userId}/revoke`), {
    method: "POST",
    headers: adminHeaders(),
  });
  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  return res.json();
}
