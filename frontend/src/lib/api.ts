// All API calls go through Next.js /gw/* rewrites, which proxy to the Go
// gateway at http://go-gateway:8080 internally. This means the browser never
// needs to resolve "go-gateway" (a Docker-internal hostname).
const API_PREFIX = "/gw";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  login:      (username: string, password: string) =>
    req<{ username: string }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout:     () => req("/auth/logout", { method: "POST" }),
  stats:      () => req<import("./types").Stats>("/api/stats"),
  trades:     (limit = 50) => req<import("./types").Trade[]>(`/api/trades?limit=${limit}`),
  positions:  () => req<import("./types").PositionsResponse>("/api/positions"),
  decisions:  (limit = 20) => req<import("./types").Decision[]>(`/api/decisions?limit=${limit}`),
  mlSignals:  (limit = 50) => req<import("./types").MLSignal[]>(`/api/ml-signals?limit=${limit}`),
  pnlHistory: () => req<import("./types").PnlPoint[]>("/api/pnl-history"),
  agents:     () => req<{ agents: import("./types").AgentStatus[] }>("/api/agents"),
};
