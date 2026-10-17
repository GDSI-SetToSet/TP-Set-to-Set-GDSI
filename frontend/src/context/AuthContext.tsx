import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AUTH_API_PATHS, AUTH_STORAGE_KEYS } from '../constants/auth';
import { api } from '../services/api';
import type { AuthResponse, User } from '../types/auth';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, role: User['role']) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const storeSession = useCallback((response: AuthResponse) => {
    localStorage.setItem(AUTH_STORAGE_KEYS.token, response.access_token);
    localStorage.setItem(AUTH_STORAGE_KEYS.user, JSON.stringify(response.user));
    setUser(response.user);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem(AUTH_STORAGE_KEYS.token);
    if (!token) {
      setLoading(false);
      return;
    }
    api.get<User>(AUTH_API_PATHS.currentUser)
      .then(({ data }) => {
        setUser(data);
        localStorage.setItem(AUTH_STORAGE_KEYS.user, JSON.stringify(data));
      })
      .catch(() => {
        localStorage.removeItem(AUTH_STORAGE_KEYS.token);
        localStorage.removeItem(AUTH_STORAGE_KEYS.user);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post<AuthResponse>(AUTH_API_PATHS.login, { email, password });
    storeSession(data);
    return data.user;
  }, [storeSession]);

  const register = useCallback(async (email: string, password: string, role: User['role']) => {
    await api.post<User>(AUTH_API_PATHS.register, { email, password, role });
    return login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try {
      if (localStorage.getItem(AUTH_STORAGE_KEYS.token)) await api.post(AUTH_API_PATHS.logout);
    } finally {
      localStorage.removeItem(AUTH_STORAGE_KEYS.token);
      localStorage.removeItem(AUTH_STORAGE_KEYS.user);
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth debe utilizarse dentro de AuthProvider.');
  return context;
}
