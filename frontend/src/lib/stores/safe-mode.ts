import { writable } from "svelte/store";

// defaults to true so first-run users get the safety net
const STORAGE_KEY = "reclaimerr_safe_mode";
const initial =
  typeof localStorage !== "undefined" &&
  localStorage.getItem(STORAGE_KEY) === "false"
    ? false
    : true;

function createSafeModeStore() {
  const { subscribe, set } = writable<boolean>(initial);
  return {
    subscribe,
    // called on every dashboard fetch so server changes propagate
    sync: (enabled: boolean) => {
      try {
        localStorage.setItem(STORAGE_KEY, enabled ? "true" : "false");
      } catch {
        // ignore - localStorage unavailable
      }
      set(enabled);
    },
  };
}

export const safeMode = createSafeModeStore();
