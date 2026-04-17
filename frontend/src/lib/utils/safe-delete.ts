import { toast } from "svelte-sonner";

/**
 * Run a destructive action behind a 5-second Undo countdown.
 *
 * When safe-mode is on we surface a toast with a countdown and an Undo
 * button. The actual `action` only fires if the user doesn't click Undo
 * before the timer elapses. When safe-mode is off the action fires
 * immediately with no intermediate UI.
 */
export async function safeDelete({
  safeMode,
  label,
  action,
  onSuccess,
  durationMs = 5000,
}: {
  safeMode: boolean;
  label: string;
  action: () => Promise<void>;
  onSuccess?: () => void;
  durationMs?: number;
}): Promise<void> {
  if (!safeMode) {
    await action();
    onSuccess?.();
    return;
  }

  return new Promise<void>((resolve) => {
    let cancelled = false;

    const toastId = toast(`Deleting ${label}...`, {
      description: `You have ${Math.round(durationMs / 1000)} seconds to undo.`,
      duration: durationMs,
      action: {
        label: "Undo",
        onClick: () => {
          cancelled = true;
          toast.info(`Cancelled - ${label} kept.`);
          resolve();
        },
      },
    });

    setTimeout(async () => {
      if (cancelled) return;
      toast.dismiss(toastId);
      try {
        await action();
        onSuccess?.();
      } catch (e: any) {
        toast.error(e?.message ?? "Delete failed.");
      }
      resolve();
    }, durationMs);
  });
}
