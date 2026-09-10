"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiPost } from "../lib/api";
import type { AuthResponse, AuthUser } from "../lib/types";

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  refresh: () => Promise<AuthUser | null>;
  login: (email: string, password: string) => Promise<AuthUser>;
  signup: (
    email: string,
    password: string,
    displayName?: string,
    legal?: { termsVersion: string; privacyVersion: string } | null,
  ) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const AUTH_SYNC_KEY = "farelin_auth_sync";
const AUTH_REFRESH_LOCK = "farelin_auth_refresh";

let refreshPromise: Promise<AuthUser> | null = null;

async function readCurrentUser(): Promise<AuthUser> {
  const data = await apiGet<AuthResponse>("/auth/me");
  return data.user;
}

async function rotateExpiredSession(): Promise<AuthUser> {
  // A second tab may have refreshed while this tab waited for the browser
  // lock. Re-check first so two tabs never rotate the same token together.
  try {
    return await readCurrentUser();
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
  }

  const data = await apiPost<AuthResponse>("/auth/refresh");
  return data.user;
}

async function restoreSession(): Promise<AuthUser | null> {
  try {
    return await readCurrentUser();
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) return null;
  }

  try {
    // Web Locks coordinate refresh-token rotation across tabs. The module-level
    // promise is the fallback and also deduplicates calls inside this tab.
    if (typeof navigator !== "undefined" && navigator.locks) {
      return await navigator.locks.request(AUTH_REFRESH_LOCK, rotateExpiredSession);
    }
    if (!refreshPromise) {
      refreshPromise = rotateExpiredSession().finally(() => {
        refreshPromise = null;
      });
    }
    return await refreshPromise;
  } catch {
    return null;
  }
}

/**
 * Tell other tabs that the browser's HttpOnly session changed.
 *
 * The stored value is only an event nonce; no user data or credential is ever
 * exposed to JavaScript or localStorage.
 */
export function announceAuthChange() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      AUTH_SYNC_KEY,
      `${Date.now()}:${typeof crypto.randomUUID === "function" ? crypto.randomUUID() : "changed"}`,
    );
  } catch {
    // Storage can be unavailable in strict privacy modes. Session cookies and
    // the next page load still restore the correct account in that case.
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const stateRevision = useRef(0);

  const refresh = useCallback(async () => {
    const revision = ++stateRevision.current;
    const restoredUser = await restoreSession();
    if (revision === stateRevision.current) {
      setUser(restoredUser);
      setIsLoading(false);
    }
    return restoredUser;
  }, []);

  useEffect(() => {
    void refresh();
    const syncFromAnotherTab = (event: StorageEvent) => {
      if (event.key === AUTH_SYNC_KEY && event.newValue) void refresh();
    };
    window.addEventListener("storage", syncFromAnotherTab);
    return () => window.removeEventListener("storage", syncFromAnotherTab);
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiPost<AuthResponse>("/auth/login", { email, password });
    stateRevision.current += 1;
    setUser(data.user);
    setIsLoading(false);
    announceAuthChange();
    return data.user;
  }, []);

  const signup = useCallback(
    async (
      email: string,
      password: string,
      displayName?: string,
      legal?: { termsVersion: string; privacyVersion: string } | null,
    ) => {
      const data = await apiPost<AuthResponse>("/auth/signup", {
        email,
        password,
        displayName: displayName || undefined,
        acceptedTermsVersion: legal?.termsVersion,
        acknowledgedPrivacyVersion: legal?.privacyVersion,
      });
      stateRevision.current += 1;
      setUser(data.user);
      setIsLoading(false);
      announceAuthChange();
      return data.user;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await apiPost("/auth/logout");
    } finally {
      stateRevision.current += 1;
      setUser(null);
      setIsLoading(false);
      announceAuthChange();
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, refresh, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
