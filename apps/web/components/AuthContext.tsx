"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { apiGet, apiPost } from "../lib/api";
import type { AuthResponse, AuthUser } from "../lib/types";

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<AuthUser>;
  signup: (email: string, password: string, displayName?: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<AuthResponse>("/auth/me");
      setUser(data.user);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiPost<AuthResponse>("/auth/login", { email, password });
    setUser(data.user);
    return data.user;
  }, []);

  const signup = useCallback(async (email: string, password: string, displayName?: string) => {
    const data = await apiPost<AuthResponse>("/auth/signup", {
      email,
      password,
      displayName: displayName || undefined,
    });
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiPost("/auth/logout");
    } finally {
      setUser(null);
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
