export interface User {
  id: number;
  username: string;
  display_name: string | null;
  email: string | null;
  role: string;
}

export interface UserProfile extends User {
  avatar_url: string | null;
  created_at: string;
}
