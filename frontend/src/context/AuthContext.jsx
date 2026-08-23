import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import { setTokens, clearTokens, getAccessToken } from "../api/tokenStorage";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const { user: me } = await api.auth.me();
      setUser(me);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
    const onLogout = () => setUser(null);
    window.addEventListener("billio:logout", onLogout);
    return () => window.removeEventListener("billio:logout", onLogout);
  }, [loadMe]);

  const login = useCallback(async (username, password) => {
    const result = await api.auth.login({ username, password });
    setTokens(result);
    setUser(result.user);
    return result.user;
  }, []);

  const signup = useCallback(async (data) => {
    const result = await api.auth.signup(data);
    setTokens(result);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // Still clear locally even if the network call fails.
    }
    clearTokens();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const { user: me } = await api.auth.me();
    setUser(me);
    return me;
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refreshUser, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
