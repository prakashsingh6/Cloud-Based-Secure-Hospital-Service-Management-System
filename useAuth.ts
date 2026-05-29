import { useState, useEffect, useCallback } from 'react';
import type { User, UserRole, AuthState } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? 'Request failed');
  }

  return response.json();
};

export const useAuth = () => {
  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    user: null,
    token: null
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const storedToken = localStorage.getItem('zetatech_token');
    const storedUser = localStorage.getItem('zetatech_user');

    const restoreSession = async () => {
      if (!storedToken || !storedUser) {
        setIsLoading(false);
        return;
      }

      try {
        const user = await apiFetch<User>('/auth/me', {
          headers: {
            Authorization: `Bearer ${storedToken}`
          }
        });

        if (!isMounted) {
          return;
        }

        localStorage.setItem('zetatech_user', JSON.stringify(user));
        setAuthState({
          isAuthenticated: true,
          user,
          token: storedToken
        });
      } catch {
        localStorage.removeItem('zetatech_token');
        localStorage.removeItem('zetatech_user');
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    restoreSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const result = await apiFetch<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });

      localStorage.setItem('zetatech_token', result.access_token);
      localStorage.setItem('zetatech_user', JSON.stringify(result.user));

      setAuthState({
        isAuthenticated: true,
        user: result.user,
        token: result.access_token
      });

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Login failed'
      };
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('zetatech_token');
    localStorage.removeItem('zetatech_user');
    setAuthState({
      isAuthenticated: false,
      user: null,
      token: null
    });
  }, []);

  const hasRole = useCallback((role: UserRole): boolean => {
    return authState.user?.role === role;
  }, [authState.user]);

  return {
    ...authState,
    isLoading,
    login,
    logout,
    hasRole
  };
};
