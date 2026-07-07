const STORAGE_KEY = "sa_admin_key";

export function getAdminKey(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(STORAGE_KEY);
}

export function setAdminKey(key: string): void {
  sessionStorage.setItem(STORAGE_KEY, key);
}

export function clearAdminKey(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
