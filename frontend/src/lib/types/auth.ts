import type { UserProfile } from "$lib/types/shared";

export interface AuthState {
  isAuthenticated: boolean;
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
}
