import { create } from "zustand";
import { persist } from "zustand/middleware";
import { login as apiLogin, logout as apiLogout } from "@/lib/api";

interface User {
  id: string;
  name: string;
  email: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  setToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiLogin({ email, password });
          localStorage.setItem("dockguard_auth_token", response.token);
          set({
            token: response.token,
            user: response.user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (err) {
          const message =
            err instanceof Error ? err.message : "Login failed";
          set({ error: message, isLoading: false });
          throw err;
        }
      },

      logout: async () => {
        try {
          await apiLogout();
        } catch {
          // Continue with local logout even if API call fails
        }
        localStorage.removeItem("dockguard_auth_token");
        set({
          token: null,
          user: null,
          isAuthenticated: false,
        });
      },

      clearError: () => set({ error: null }),

      setToken: (token: string) => {
        localStorage.setItem("dockguard_auth_token", token);
        set({ token, isAuthenticated: true });
      },
    }),
    {
      name: "dockguard-auth",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
