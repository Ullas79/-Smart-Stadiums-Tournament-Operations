import type { ChatResponse, Role, RoleInfo, StadiumSnapshot } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchRoles(): Promise<{ roles: RoleInfo[] }> {
  return jsonFetch("/role");
}

export function fetchState(): Promise<StadiumSnapshot> {
  return jsonFetch("/state");
}

export function sendChat(
  message: string,
  role: Role,
  history: { role: "user" | "assistant"; content: string }[],
  language: string
): Promise<ChatResponse> {
  return jsonFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message, role, history, language }),
  });
}
