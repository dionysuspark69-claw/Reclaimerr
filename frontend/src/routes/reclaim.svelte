<script lang="ts">
  import { onMount } from "svelte";
  import { push } from "svelte-spa-router";
  import { get_api } from "$lib/api";
  import ErrorBox from "$lib/components/error-box.svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import type {
    DashboardResponse,
    PaginatedDuplicatesResponse,
  } from "$lib/types/shared";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Copy from "@lucide/svelte/icons/copy";
  import HardDriveDownload from "@lucide/svelte/icons/hard-drive-download";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";

  let dashboard = $state<DashboardResponse | null>(null);
  let duplicates = $state<PaginatedDuplicatesResponse | null>(null);
  let loading = $state(true);
  let error = $state("");

  const candidateGb = $derived(
    dashboard?.kpis.reclaimable_total_gb ?? 0,
  );
  const duplicateGb = $derived(
    duplicates ? duplicates.total_reclaimable_bytes / 1024 / 1024 / 1024 : 0,
  );
  const totalGb = $derived(candidateGb + duplicateGb);

  const load = async () => {
    loading = true;
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

  onMount(load);
</script>

<div class="p-2.5 md:p-8 max-w-7xl mx-auto space-y-6">
  <div class="space-y-2">
    <h1 class="text-3xl font-bold text-foreground">Reclaim Space</h1>
    <p class="text-muted-foreground">
      Everything you can free up right now, grouped by source.
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
    <!-- hero total -->
    <div
      class="bg-gradient-to-br from-primary/15 via-card to-card rounded-lg border border-primary/40 p-6
        md:p-8"
    >
      <p class="text-sm uppercase tracking-wider text-muted-foreground">
        Total reclaimable
      </p>
      <p class="text-5xl md:text-6xl font-bold text-primary mt-2">
        {totalGb.toFixed(2)} <span class="text-3xl">GB</span>
      </p>
      <p class="text-muted-foreground mt-2">
        {candidateGb.toFixed(2)} GB from cleanup rules · {duplicateGb.toFixed(2)}
        GB from duplicates
      </p>
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
                Media flagged by your rules and Tdarr.
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
                Cross-library and multi-version copies of the same title.
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

    <!-- tdarr explainer -->
    <div class="bg-card rounded-lg border border-border p-5">
      <div class="flex gap-4 items-start">
        <div
          class="size-10 rounded-lg bg-purple-500/15 text-purple-400 flex items-center justify-center
            shrink-0"
        >
          <HardDriveDownload class="size-5" />
        </div>
        <div class="flex-1">
          <h3 class="font-semibold text-foreground">Tdarr integration</h3>
          <p class="text-sm text-muted-foreground mt-1">
            Files Tdarr has flagged for transcode appear in <strong
              >Cleanup candidates</strong
            >
            with reason "Tdarr flagged". Configure Tdarr in
            <button
              class="text-primary underline cursor-pointer"
              onclick={() => push("/settings")}>Settings</button
            > to surface them.
          </p>
        </div>
      </div>
    </div>
  {/if}
</div>
