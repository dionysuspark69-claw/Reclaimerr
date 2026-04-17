<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { push } from "svelte-spa-router";
  import { get_api, post_api } from "$lib/api";
  import ErrorBox from "$lib/components/error-box.svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { auth } from "$lib/stores/auth";
  import {
    BackgroundJobStatus,
    UserRole,
    Permission,
    type DashboardResponse,
    type PaginatedDuplicatesResponse,
  } from "$lib/types/shared";
  import { toast } from "svelte-sonner";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Copy from "@lucide/svelte/icons/copy";
  import HardDriveDownload from "@lucide/svelte/icons/hard-drive-download";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Settings from "@lucide/svelte/icons/settings";

  let dashboard = $state<DashboardResponse | null>(null);
  let duplicates = $state<PaginatedDuplicatesResponse | null>(null);
  let loading = $state(true);
  let error = $state("");
  let scanning = $state(false);

  // Per-task live status during "Scan everything".
  type ScanStage = "idle" | "queued" | "running" | "done" | "failed";
  let scanStages = $state<Record<string, ScanStage>>({
    scan_cleanup_candidates: "idle",
    find_duplicates: "idle",
    scan_tdarr_flagged: "idle",
  });
  let scanPollTimer: ReturnType<typeof setTimeout> | null = null;

  const candidateGb = $derived(dashboard?.kpis.reclaimable_total_gb ?? 0);
  const duplicateGb = $derived(
    duplicates ? duplicates.total_reclaimable_bytes / 1024 / 1024 / 1024 : 0,
  );
  const totalGb = $derived(candidateGb + duplicateGb);

  const tdarrService = $derived(
    dashboard?.services?.find((s) => s.name === "tdarr") ?? null,
  );
  const tdarrConfigured = $derived(!!tdarrService?.enabled);

  const canScan = $derived(
    $auth.user?.role === UserRole.Admin ||
      ($auth.user?.permissions ?? []).includes(Permission.ManageReclaim),
  );

  const stopPolling = () => {
    if (scanPollTimer) {
      clearTimeout(scanPollTimer);
      scanPollTimer = null;
    }
  };

  const allStagesDone = () =>
    Object.values(scanStages).every(
      (s) => s === "idle" || s === "done" || s === "failed",
    );

  const pollJobs = async (jobMap: Record<string, number | null>) => {
    const pairs = Object.entries(jobMap).filter(
      ([, jobId]) => jobId !== null,
    ) as [string, number][];

    try {
      const results = await Promise.all(
        pairs.map(([task, jobId]) =>
          get_api<{ id: number; status: BackgroundJobStatus }>(
            `/api/tasks/background-jobs/${jobId}/status`,
          ).then((r) => ({ task, result: r })),
        ),
      );

      for (const { task, result } of results) {
        if (result.status === BackgroundJobStatus.Completed) {
          scanStages[task] = "done";
        } else if (
          result.status === BackgroundJobStatus.Failed ||
          result.status === BackgroundJobStatus.Canceled
        ) {
          scanStages[task] = "failed";
        } else if (result.status === BackgroundJobStatus.Running) {
          scanStages[task] = "running";
        }
      }

      if (allStagesDone()) {
        stopPolling();
        scanning = false;
        const failures = Object.entries(scanStages).filter(
          ([, s]) => s === "failed",
        );
        if (failures.length > 0) {
          toast.error(`${failures.length} scan(s) failed — check Tasks.`);
        } else {
          toast.success("All scans complete.");
        }
        // refresh the hub numbers
        await load(false);
      } else {
        scanPollTimer = setTimeout(() => pollJobs(jobMap), 2000);
      }
    } catch (e: any) {
      stopPolling();
      scanning = false;
      toast.error(e.message ?? "Lost track of scan progress.");
    }
  };

  const scanEverything = async () => {
    scanning = true;
    scanStages = {
      scan_cleanup_candidates: "queued",
      find_duplicates: "queued",
      scan_tdarr_flagged: tdarrConfigured ? "queued" : "idle",
    };
    stopPolling();

    try {
      const resp = await post_api<{
        jobs: Record<string, { queued: boolean; job_id: number | null }>;
        tdarr_configured: boolean;
      }>("/api/media/scan-everything", {});

      const jobMap: Record<string, number | null> = {};
      for (const [task, info] of Object.entries(resp.jobs)) {
        jobMap[task] = info.job_id;
        if (info.job_id === null) scanStages[task] = "done";
      }

      if (Object.values(jobMap).every((v) => v === null)) {
        scanning = false;
        toast.info("All scans are already running or up to date.");
        return;
      }

      scanPollTimer = setTimeout(() => pollJobs(jobMap), 1500);
    } catch (e: any) {
      scanning = false;
      scanStages = {
        scan_cleanup_candidates: "idle",
        find_duplicates: "idle",
        scan_tdarr_flagged: "idle",
      };
      toast.error(e.message ?? "Failed to start scans.");
    }
  };

  const stageLabel = (stage: ScanStage): string =>
    ({
      idle: "—",
      queued: "Queued…",
      running: "Scanning…",
      done: "Done",
      failed: "Failed",
    })[stage];

  const stageClass = (stage: ScanStage): string =>
    ({
      idle: "text-muted-foreground",
      queued: "text-amber-400",
      running: "text-primary",
      done: "text-emerald-400",
      failed: "text-destructive",
    })[stage];

  const load = async (showSpinner = true) => {
    if (showSpinner) loading = true;
    error = "";
    try {
      const [dash, dups] = await Promise.all([
        get_api<DashboardResponse>("/api/dashboard"),
        get_api<PaginatedDuplicatesResponse>(
          "/api/media/duplicates?page=1&per_page=1",
        ),
      ]);
      dashboard = dash;
      duplicates = dups;
    } catch (e: any) {
      error = e.message ?? "Failed to load reclaim summary.";
    } finally {
      loading = false;
    }
  };

  onMount(() => load());
  onDestroy(stopPolling);
</script>

<div class="p-2.5 md:p-8 max-w-7xl mx-auto space-y-6">
  <div class="space-y-2">
    <h1 class="text-3xl font-bold text-foreground">Free up space</h1>
    <p class="text-muted-foreground">
      Everything you can delete right now, grouped by source.
    </p>
  </div>

  <ErrorBox {error} />

  {#if loading}
    <div
      class="bg-card rounded-lg border border-border p-12 text-center text-muted-foreground"
    >
      <div
        class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary
          border-r-transparent"
      ></div>
      <p class="mt-4">Loading reclaim summary...</p>
    </div>
  {:else}
    <!-- hero total + scan action -->
    <div
      class="bg-gradient-to-br from-primary/15 via-card to-card rounded-lg border border-primary/40 p-6
        md:p-8"
    >
      <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p class="text-sm uppercase tracking-wider text-muted-foreground">
            Total reclaimable
          </p>
          <p class="text-5xl md:text-6xl font-bold text-primary mt-2">
            {totalGb.toFixed(2)} <span class="text-3xl">GB</span>
          </p>
          <p class="text-muted-foreground mt-2">
            {candidateGb.toFixed(2)} GB from cleanup rules ·
            {duplicateGb.toFixed(2)} GB from duplicates
          </p>
        </div>
        {#if canScan}
          <div class="flex flex-col items-stretch md:items-end gap-2">
            <Button onclick={scanEverything} disabled={scanning} class="cursor-pointer gap-2">
              <RefreshCw class="size-4 {scanning ? 'animate-spin' : ''}" />
              {scanning ? "Scanning..." : "Scan everything now"}
            </Button>
            {#if scanning || Object.values(scanStages).some((s) => s !== "idle")}
              <div class="text-xs text-right space-y-0.5 min-w-[180px]">
                <div class="flex justify-between gap-4">
                  <span class="text-muted-foreground">Cleanup rules</span>
                  <span class={stageClass(scanStages.scan_cleanup_candidates)}
                    >{stageLabel(scanStages.scan_cleanup_candidates)}</span
                  >
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-muted-foreground">Duplicates</span>
                  <span class={stageClass(scanStages.find_duplicates)}
                    >{stageLabel(scanStages.find_duplicates)}</span
                  >
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-muted-foreground">Tdarr</span>
                  {#if tdarrConfigured}
                    <span class={stageClass(scanStages.scan_tdarr_flagged)}
                      >{stageLabel(scanStages.scan_tdarr_flagged)}</span
                    >
                  {:else}
                    <span class="text-muted-foreground italic">Not configured</span>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>

    <!-- source cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <button
        type="button"
        onclick={() => push("/candidates")}
        class="group text-left bg-card rounded-lg border border-border p-6 hover:border-primary/50
          hover:bg-accent/30 transition-colors cursor-pointer"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex gap-4">
            <div
              class="size-12 rounded-lg bg-amber-500/15 text-amber-400 flex items-center justify-center
                shrink-0"
            >
              <TriangleAlert class="size-6" />
            </div>
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                Cleanup candidates
              </h2>
              <p class="text-sm text-muted-foreground mt-1">
                Media flagged for deletion by your rules{tdarrConfigured
                  ? " or Tdarr"
                  : ""}.
              </p>
              <p class="text-2xl font-bold text-foreground mt-3">
                {candidateGb.toFixed(2)} <span class="text-base">GB</span>
              </p>
            </div>
          </div>
          <ChevronRight
            class="size-5 text-muted-foreground transition-transform group-hover:translate-x-1"
          />
        </div>
      </button>

      <button
        type="button"
        onclick={() => push("/duplicates")}
        class="group text-left bg-card rounded-lg border border-border p-6 hover:border-primary/50
          hover:bg-accent/30 transition-colors cursor-pointer"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex gap-4">
            <div
              class="size-12 rounded-lg bg-blue-500/15 text-blue-400 flex items-center justify-center
                shrink-0"
            >
              <Copy class="size-6" />
            </div>
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                Duplicates
              </h2>
              <p class="text-sm text-muted-foreground mt-1">
                The same title stored more than once (different libraries or
                file versions).
              </p>
              <p class="text-2xl font-bold text-foreground mt-3">
                {duplicateGb.toFixed(2)} <span class="text-base">GB</span>
                {#if duplicates && duplicates.total > 0}
                  <span class="text-sm text-muted-foreground font-normal">
                    · {duplicates.total} group{duplicates.total !== 1 ? "s" : ""}
                  </span>
                {/if}
              </p>
            </div>
          </div>
          <ChevronRight
            class="size-5 text-muted-foreground transition-transform group-hover:translate-x-1"
          />
        </div>
      </button>
    </div>

    <!-- tdarr status card -->
    <div
      class="bg-card rounded-lg border {tdarrConfigured
        ? 'border-border'
        : 'border-dashed border-muted-foreground/30'} p-5"
    >
      <div class="flex gap-4 items-start">
        <div
          class="size-10 rounded-lg bg-purple-500/15 text-purple-400 flex items-center justify-center
            shrink-0"
        >
          <HardDriveDownload class="size-5" />
        </div>
        <div class="flex-1">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <h3 class="font-semibold text-foreground">
                Tdarr —
                {#if tdarrConfigured}
                  <span class="text-emerald-400">connected</span>
                {:else}
                  <span class="text-muted-foreground">not configured</span>
                {/if}
              </h3>
              <p class="text-sm text-muted-foreground mt-1">
                {#if tdarrConfigured}
                  Files Tdarr has flagged for transcode are added to <strong
                    >Cleanup candidates</strong
                  > with reason "Tdarr flagged" every scan.
                {:else}
                  Hook up Tdarr and its flagged files become a reclaim source
                  automatically. Nothing else to do — just point us at your
                  Tdarr server.
                {/if}
              </p>
            </div>
            {#if !tdarrConfigured && $auth.user?.role === UserRole.Admin}
              <Button
                variant="outline"
                onclick={() => push("/settings")}
                class="cursor-pointer gap-2 shrink-0"
              >
                <Settings class="size-4" />
                Set up Tdarr
              </Button>
            {/if}
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
