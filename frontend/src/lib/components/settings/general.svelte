<script lang="ts">
  import { onMount } from "svelte";
  import type { Component } from "svelte";
  import { Label } from "$lib/components/ui/label/index.js";
  import { Checkbox } from "$lib/components/ui/checkbox/index.js";
  import { Input } from "$lib/components/ui/input/index.js";
  import * as Select from "$lib/components/ui/select/index.js";
  import { get_api, put_api } from "$lib/api";
  import { safeMode } from "$lib/stores/safe-mode";
  import { toast } from "svelte-sonner";
  import { Button } from "$lib/components/ui/button/index.js";
  import Save from "@lucide/svelte/icons/save";
  import Spinner from "$lib/components/ui/spinner/spinner.svelte";
  import {
    type GeneralSettings,
    type LibraryOption,
  } from "$lib/types/shared";

  // props
  interface Props {
    svgIcon: Component | null;
  }
  let { svgIcon }: Props = $props();

  // state
  let loading = $state(true);
  let savingSettings = $state(false);
  let aarrTagging = $state({
    autoTagEnabled: false,
    cleanupTagSuffix: "",
    workerPollMinSeconds: "",
    workerPollMaxSeconds: "",
  });
  let safety = $state({
    safeModeEnabled: true,
    preferredLibraryId: "",
  });
  let libraries = $state<LibraryOption[]>([]);

  const PREFERRED_NONE = "__none__";

  const parseOptionalSeconds = (value: string): number | null => {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  // save settings
  const saveSettings = async () => {
    savingSettings = true;
    try {
      // validate input before saving
      const validationError = validateCleanupTagSuffix();
      if (validationError) throw new Error(validationError);

      const preferredLibraryId =
        safety.preferredLibraryId === PREFERRED_NONE ||
        !safety.preferredLibraryId
          ? null
          : safety.preferredLibraryId;

      // save settings to backend
      await put_api("/api/settings/general", {
        auto_tag_enabled: aarrTagging.autoTagEnabled,
        cleanup_tag_suffix: aarrTagging.cleanupTagSuffix,
        worker_poll_min_seconds: parseOptionalSeconds(
          aarrTagging.workerPollMinSeconds,
        ),
        worker_poll_max_seconds: parseOptionalSeconds(
          aarrTagging.workerPollMaxSeconds,
        ),
        safe_mode_enabled: safety.safeModeEnabled,
        preferred_library_id: preferredLibraryId,
      });
      safeMode.sync(safety.safeModeEnabled);
      toast.success("General settings saved");
    } catch (error) {
      console.error("Error saving general settings:", error);
      toast.error(
        `Failed to save general settings: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      savingSettings = false;
    }
  };

  // check cleanup tag suffix for invalid characters and notify user if not valid
  const validateCleanupTagSuffix = (): string | void => {
    // allow empty suffix
    if (aarrTagging.cleanupTagSuffix) {
      // must start with hyphen or underscore, and only contain allowed chars
      const valid = /^[-_][a-z_-]*$/.test(aarrTagging.cleanupTagSuffix);
      if (!valid) {
        return (
          "Cleanup tag suffix must start with a hyphen or underscore and only contain lowercase letters, " +
          "underscores, or hyphens"
        );
      }
    }

    const workerPollMinSeconds = parseOptionalSeconds(
      aarrTagging.workerPollMinSeconds,
    );
    const workerPollMaxSeconds = parseOptionalSeconds(
      aarrTagging.workerPollMaxSeconds,
    );

    if (
      aarrTagging.workerPollMinSeconds.trim() &&
      workerPollMinSeconds === null
    ) {
      return "Worker poll minimum must be a valid number of seconds";
    }

    if (
      aarrTagging.workerPollMaxSeconds.trim() &&
      workerPollMaxSeconds === null
    ) {
      return "Worker poll maximum must be a valid number of seconds";
    }

    if (workerPollMinSeconds !== null && workerPollMinSeconds <= 0) {
      return "Worker poll minimum must be greater than 0 seconds";
    }

    if (workerPollMinSeconds !== null && workerPollMinSeconds > 60) {
      return "Worker poll minimum cannot exceed 60 seconds";
    }

    if (workerPollMaxSeconds !== null && workerPollMaxSeconds <= 0) {
      return "Worker poll maximum must be greater than 0 seconds";
    }

    if (workerPollMaxSeconds !== null && workerPollMaxSeconds > 60) {
      return "Worker poll maximum cannot exceed 60 seconds";
    }

    if (
      workerPollMinSeconds !== null &&
      workerPollMaxSeconds !== null &&
      workerPollMinSeconds > workerPollMaxSeconds
    ) {
      return "Worker poll minimum cannot be greater than worker poll maximum";
    }
  };

  onMount(async () => {
    try {
      const [settings, libs] = await Promise.all([
        get_api<GeneralSettings>("/api/settings/general"),
        get_api<LibraryOption[]>("/api/settings/libraries").catch(() => []),
      ]);
      if (settings) {
        aarrTagging = {
          autoTagEnabled: settings.auto_tag_enabled,
          cleanupTagSuffix: settings.cleanup_tag_suffix,
          workerPollMinSeconds:
            settings.worker_poll_min_seconds?.toString() ?? "",
          workerPollMaxSeconds:
            settings.worker_poll_max_seconds?.toString() ?? "",
        };
        safety = {
          safeModeEnabled: settings.safe_mode_enabled,
          preferredLibraryId: settings.preferred_library_id ?? PREFERRED_NONE,
        };
        safeMode.sync(settings.safe_mode_enabled);
      }
      libraries = Array.isArray(libs) ? libs : [];
    } catch (error) {
      console.error("Error fetching general settings:", error);
      toast.error("Failed to load general settings");
    } finally {
      loading = false;
    }
  });
</script>

<div class="space-y-6">
  <!-- header -->
  <div>
    <h2 class="flex items-center gap-3 text-xl font-semibold text-foreground">
      {#if svgIcon}
        {@const Icon = svgIcon}
        <Icon class="size-5" aria-hidden="true" />
      {/if}
      General
    </h2>
    <p class="text-sm text-muted-foreground mt-1">Manage general settings</p>
  </div>

  <!-- check if loading -->
  {#if loading}
    <div class="flex justify-center py-8">
      <Spinner />
    </div>
  {:else}
    <!-- arr tagging -->
    <div class="bg-muted/50 border rounded-lg p-4 shadow-sm mt-6">
      <h3 class="font-semibold text-foreground items-center mb-3">
        Radarr and Sonarr tagging
      </h3>

      <!-- automatic tagging toggle -->
      <div class="flex gap-2 items-center mb-4">
        <Checkbox
          id="autoTagEnabled"
          name="autoTagEnabled"
          class="cursor-pointer"
          bind:checked={aarrTagging.autoTagEnabled}
        />
        <Label
          for="autoTagEnabled"
          class="inline-flex items-center gap-2 cursor-pointer"
        >
          <span class="text-sm text-foreground"
            >Enable automatic tagging of reclaimerr candidates</span
          >
        </Label>
      </div>

      <!-- cleanup tag suffix -->
      <div>
        <Label for="cleanupTagSuffix" class="mb-2">
          <span class="text-sm text-foreground">Cleanup Tag Suffix</span>
        </Label>
        <Input
          id="cleanupTagSuffix"
          name="cleanupTagSuffix"
          type="text"
          class="input-hover-el text-foreground placeholder:text-muted-foreground"
          placeholder="e.g. '-candidate'"
          maxlength={15}
          bind:value={aarrTagging.cleanupTagSuffix}
        />
        <p class="mt-1 text-xs text-muted-foreground">
          Optional suffix for cleanup tag (base: 'reclaimerr'). Example:
          '-candidate' -> 'reclaimerr-candidate'
        </p>
        <p class="mt-1 text-xs text-muted-foreground">
          Note: modifying this will update existing tags during the <span
            class="font-bold">Tag Cleanup Candidates</span
          > task.
        </p>
      </div>
    </div>

    <div class="bg-muted/50 border rounded-lg p-4 shadow-sm mt-6">
      <h3 class="font-semibold text-foreground items-center">Worker polling</h3>
      <p class="text-muted-foreground text-sm mb-3">
        Configure the background worker's polling behavior when idle. Adjusting
        these settings can help balance prompt job processing with resource
        usage. Recommended values are between 0.5 and 5 seconds (max 60
        seconds).
      </p>

      <div class="grid gap-4 md:grid-cols-2">
        <!-- minimum poll seconds -->
        <div>
          <Label for="workerPollMinSeconds" class="mb-2">
            <span class="text-sm text-foreground">Minimum Poll Seconds</span>
          </Label>
          <Input
            id="workerPollMinSeconds"
            name="workerPollMinSeconds"
            type="number"
            min="0.1"
            max="60"
            step="0.1"
            class="input-hover-el text-foreground placeholder:text-muted-foreground"
            placeholder="Default: 0.5"
            bind:value={aarrTagging.workerPollMinSeconds}
          />
        </div>

        <!-- maximum poll seconds -->
        <div>
          <Label for="workerPollMaxSeconds" class="mb-2">
            <span class="text-sm text-foreground">Maximum Poll Seconds</span>
          </Label>
          <Input
            id="workerPollMaxSeconds"
            name="workerPollMaxSeconds"
            type="number"
            min="0.1"
            max="60"
            step="0.1"
            class="input-hover-el text-foreground placeholder:text-muted-foreground"
            placeholder="Default: 5"
            bind:value={aarrTagging.workerPollMaxSeconds}
          />
        </div>
      </div>
    </div>

    <!-- safety & duplicate preferences -->
    <div class="bg-muted/50 border rounded-lg p-4 shadow-sm mt-6">
      <h3 class="font-semibold text-foreground items-center mb-3">
        Safety &amp; duplicate preferences
      </h3>

      <!-- safe mode toggle -->
      <div class="flex gap-2 items-start mb-4">
        <Checkbox
          id="safeModeEnabled"
          name="safeModeEnabled"
          class="cursor-pointer mt-0.5"
          bind:checked={safety.safeModeEnabled}
        />
        <Label
          for="safeModeEnabled"
          class="inline-flex flex-col items-start gap-1 cursor-pointer"
        >
          <span class="text-sm text-foreground">Enable safe mode</span>
          <span class="text-xs text-muted-foreground font-normal">
            Show a 5-second undo countdown after any delete action. Gives you
            a chance to cancel an accidental click.
          </span>
        </Label>
      </div>

      <!-- preferred library -->
      <div>
        <Label for="preferredLibrary" class="mb-2">
          <span class="text-sm text-foreground">Preferred library</span>
        </Label>
        <Select.Root
          type="single"
          bind:value={safety.preferredLibraryId}
        >
          <Select.Trigger
            id="preferredLibrary"
            class="input-hover-el text-foreground"
          >
            {#if safety.preferredLibraryId && safety.preferredLibraryId !== PREFERRED_NONE}
              {libraries.find(
                (l) => l.library_id === safety.preferredLibraryId,
              )?.library_name ?? safety.preferredLibraryId}
            {:else}
              No preference
            {/if}
          </Select.Trigger>
          <Select.Content>
            <Select.Item value={PREFERRED_NONE} label="No preference">
              No preference
            </Select.Item>
            {#each libraries as lib (lib.library_id)}
              <Select.Item
                value={lib.library_id}
                label={lib.library_name}
              >
                {lib.library_name}
              </Select.Item>
            {/each}
          </Select.Content>
        </Select.Root>
        <p class="mt-1 text-xs text-muted-foreground">
          When a movie exists in multiple libraries, Reclaimerr will suggest
          keeping the copy in this library. Resolution and file size still
          apply as tie-breakers within other libraries.
        </p>
      </div>
    </div>

    <!-- save -->
    <div class="flex gap-3 justify-end">
      <Button
        onclick={saveSettings}
        disabled={savingSettings}
        class="cursor-pointer gap-2"
      >
        {#if savingSettings}
          <Spinner class="size-4" />
        {:else}
          <Save class="size-4" />
        {/if}
        Save
      </Button>
    </div>
  {/if}
</div>
