export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) return body.detail[0].msg;
    return JSON.stringify(body);
  } catch {
    return response.statusText || "Request failed.";
  }
}

const CSRF_COOKIE = "triplet_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Read the CSRF token the API issued.
 *
 * The cookie is deliberately not HttpOnly: echoing it back in a header is the
 * whole mechanism, and a page on another origin cannot read it. The token grants
 * nothing on its own — it only proves the request came from a Triplet page.
 */
function csrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

let cachedToken: string | null = null;

/**
 * The token to echo back on a state-changing request.
 *
 * Production proxies the API same-origin, so the cookie is readable and this
 * costs nothing. Local development talks cross-origin, where the page cannot
 * read a cookie set on the API's host — so the token is fetched once and kept
 * in memory instead. Both modes end up presenting the same value.
 */
async function csrfToken(): Promise<string | null> {
  const fromCookie = csrfCookie();
  if (fromCookie) return fromCookie;
  if (cachedToken) return cachedToken;
  try {
    const response = await fetch(`${apiBaseUrl}/auth/csrf`, { credentials: "include" });
    if (!response.ok) return null;
    cachedToken = ((await response.json()) as { token: string }).token;
    return cachedToken;
  } catch {
    return null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const token = UNSAFE_METHODS.has(method) ? await csrfToken() : null;

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      credentials: "include",
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { [CSRF_HEADER]: token } : {}),
        ...init?.headers,
      },
    });
  } catch {
    // fetch rejects with a bare "Failed to fetch" when the request never
    // reaches the server — offline, DNS, a blocked origin. Callers render this
    // message straight into a Notice, so without this the user was shown
    // browser-internal wording, and a screen reader now reads it aloud. Status
    // 0 is the conventional "no response" marker and lets callers tell a
    // connection problem apart from a real HTTP status.
    throw new ApiError(0, "We couldn't reach Triplet. Check your connection and try again.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  return (await response.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}
