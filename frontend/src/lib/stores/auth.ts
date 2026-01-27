import { writable } from "svelte/store";
import type { UserProfile } from "$lib/types/shared";
import type { AuthState } from "$lib/types/auth";

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({
    isAuthenticated: false,
    user: null,
    token: null,
    loading: true, // start with loading=true while we check for existing token
  });

  // initialize auth state from localStorage
  async function init() {
    const token = localStorage.getItem("authToken");
    if (token) {
      try {
        // verify token is still valid by fetching user info
        const response = await fetch("/api/account/me", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const user = await response.json();
          set({
            isAuthenticated: true,
            user,
            token,
            loading: false,
          });
        } else {
          // token invalid, clear it
          localStorage.removeItem("authToken");
          set({
            isAuthenticated: false,
            user: null,
            token: null,
            loading: false,
          });
        }
      } catch (error) {
        console.error("Failed to verify token:", error);
        localStorage.removeItem("authToken");
        set({
          isAuthenticated: false,
          user: null,
          token: null,
          loading: false,
        });
      }
    } else {
      set({
        isAuthenticated: false,
        user: null,
        token: null,
        loading: false,
      });
    }
  }

  return {
    subscribe,
    init,
    // login
    login: async (username: string, password: string) => {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Login failed");
      }

      const data = await response.json();

      // store token
      localStorage.setItem("authToken", data.access_token);

      set({
        isAuthenticated: true,
        user: data.user,
        token: data.access_token,
        loading: false,
      });

      return data;
    },

    // logout
    logout: () => {
      localStorage.removeItem("authToken");
      set({
        isAuthenticated: false,
        user: null,
        token: null,
        loading: false,
      });
    },

    // update user info (e.g., after profile update)
    updateUser: (user: UserProfile) => {
      update((state) => ({
        ...state,
        user,
      }));
    },
  };
}

export const auth = createAuthStore();
