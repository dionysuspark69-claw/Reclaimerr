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

export enum MediaType {
  Movie = "movie",
  Series = "series",
}

export enum SettingsTab {
  Jellyfin = "jellyfin",
  Plex = "plex",
  Radarr = "radarr",
  Sonarr = "sonarr",
  Seerr = "seerr",
  General = "general",
  Tasks = "tasks",
  Notifications = "notifications",
  Account = "account",
  Rules = "rules",
  Users = "users",
  About = "about",
}

export type LibraryType = {
  id: number;
  libraryId: string;
  libraryName: string;
  mediaType: MediaType;
  serviceType: SettingsTab;
  selected: boolean;
};

export interface NotificationSetting {
  id: number;
  enabled: boolean;
  name: string | null;
  url: string;
  newCleanupCandidates: boolean;
  requestApproved: boolean;
  requestDeclined: boolean;
  adminMessage: boolean;
  taskFailure: boolean;
}

export enum NotificationType {
  NewCleanupCandidates = "new_cleanup_candidates",
  RequestApproved = "request_approved",
  RequestDeclined = "request_declined",
  AdminMessage = "admin_message",
  TaskFailure = "task_failure",
}

export interface ReclaimRule {
  id: number;
  name: string;
  media_type: MediaType;
  enabled: boolean;
  library_ids: string[] | null;
  min_popularity: number | null;
  max_popularity: number | null;
  min_vote_average: number | null;
  max_vote_average: number | null;
  min_vote_count: number | null;
  max_vote_count: number | null;
  min_view_count: number | null;
  max_view_count: number | null;
  include_never_watched: boolean;
  min_days_since_added: number | null;
  max_days_since_added: number | null;
  min_days_since_last_watched: number | null;
  max_days_since_last_watched: number | null;
  min_size: number | null;
  max_size: number | null;
  auto_tag: boolean;
  created_at: string;
  updated_at: string;
}

export enum ScheduleType {
  Cron = "cron",
  Interval = "interval",
}

export enum TaskStatus {
  Scheduled = "scheduled",
  Completed = "completed",
  Error = "error",
  Running = "running",
  Disabled = "disabled",
}
