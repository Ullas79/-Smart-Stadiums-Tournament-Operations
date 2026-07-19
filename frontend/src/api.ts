import type { ChatResponse, Incident, Role, RoleInfo, StadiumSnapshot } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const errBody = await res.json();
      if (errBody && errBody.detail) {
        detail = typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail);
      }
    } catch (e) {
      // ignore
    }
    throw new Error(`Request failed: ${res.status}${detail ? ` - ${detail}` : ''}`);
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
  language: string,
  signal?: AbortSignal
): Promise<ChatResponse> {
  return jsonFetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${role}_secure_token_123`
    },
    body: JSON.stringify({ message, role, history, language }),
    signal,
  });
}

export function triggerScenario(
  scenario: string
): Promise<{ status: string; incident?: Incident | null }> {
  // Scenario triggering requires organizer role
  return jsonFetch("/simulator/scenario", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer organizer_secure_token_123`
    },
    body: JSON.stringify({ scenario }),
  });
}
