import { create } from "zustand";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: (user, token) => {
    localStorage.setItem("epms_token", token);
    localStorage.setItem("epms_user", JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem("epms_token");
    localStorage.removeItem("epms_user");
    set({ user: null, token: null, isAuthenticated: false });
    window.location.href = "/dashboard/login/";
  },
  hydrate: () => {
    const token = localStorage.getItem("epms_token");
    const raw = localStorage.getItem("epms_user");
    if (token && raw) {
      try {
        const user = JSON.parse(raw) as User;
        set({ user, token, isAuthenticated: true });
      } catch {
        localStorage.removeItem("epms_token");
        localStorage.removeItem("epms_user");
      }
    }
  },
}));
