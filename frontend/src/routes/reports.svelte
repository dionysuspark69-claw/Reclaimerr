<script lang="ts">
  import { onMount } from "svelte";
  import { get_api } from "$lib/api";
  import ErrorBox from "$lib/components/error-box.svelte";
  import {
    MediaType,
    ReclaimSource,
    type ReclaimReport,
  } from "$lib/types/shared";
  import { formatSizeToGB } from "$lib/utils/formatters";
  import { formatDistanceToNow } from "$lib/utils/date";
  import ChartLine from "@lucide/svelte/icons/chart-line";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Copy from "@lucide/svelte/icons/copy";
  import HardDriveDownload from "@lucide/svelte/icons/hard-drive-download";
  import Hand from "@lucide/svelte/icons/hand";
  import ClapperBoard from "@lucide/svelte/icons/clapperboard";
  import Tv from "@lucide/svelte/icons/tv";

  let report = $state<ReclaimReport | null>(null);
  let loading = $state(true);
  let error = $state("");

  const formatBytes = (bytes: number): string => {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    return `${n.toFixed(i < 2 ? 0 : 2)} ${units[i]}`;
  };

  const formatMonth = (ym: string): string => {
    // ym = "YYYY-MM"
    const [y, m] = ym.split("-").map(Number);
    const d = new Date(Date.UTC(y, m - 1, 1));
    return d.toLocaleDateString("en-US", {
      month: "short",
      year: "2-digit",
      timeZone: "UTC",
    });
  };

  type SourceMeta = {
    label: string;
    icon: typeof TriangleAlert;
    bar: string;
    tint: string;
  };

  const sourceMeta: Record<string, SourceMeta> = {
    [ReclaimSource.RuleBased]: {
      label: "Cleanup rules",
      icon: TriangleAlert,
      bar: "bg-amber-400",
      tint: "bg-amber-500/15 text-amber-400",
    },
    [ReclaimSource.Duplicate]: {
      label: "Duplicates",
      icon: Copy,
      bar: "bg-blue-400",
      tint: "bg-blue-500/15 text-blue-400",
    },
    [ReclaimSource.Tdarr]: {
      label: "Tdarr",
      icon: HardDriveDownload,
      bar: "bg-purple-400",
      tint: "bg-purple-500/15 text-purple-400",
    },
    [ReclaimSource.Manual]: {
      label: "Manual",
      icon: Hand,
      bar: "bg-emerald-400",
      tint: "bg-emerald-500/15 text-emerald-400",
    },
  };

  const fallbackMeta: SourceMeta = {
    label: "Other",
    icon: ChartLine,
    bar: "bg-muted-foreground",
    tint: "bg-muted text-muted-foreground",
  };

  const metaFor = (src: string): SourceMeta => sourceMeta[src] ?? fallbackMeta;

  const sourceBreakdown = $derived.by(() => {
    if (!report) return [] as Array<{
      key: string;
      meta: SourceMeta;
      count: number;
      bytes: number;
      pct: number;
    }>;
    const entries = Object.entries(report.by_source).map(([key, b]) => ({
      key,
      meta: metaFor(key),
      count: b.count,
      bytes: b.bytes,
    }));
    const max = entries.reduce((m, e) => Math.max(m, e.bytes), 0) || 1;
    return entries
      .map((e) => ({ ...e, pct: (e.bytes / max) * 100 }))
      .sort((a, b) => b.bytes - a.bytes);
  });

  const histogramMax = $derived(
    report
      ? Math.max(1, ...report.monthly_histogram.map((b) => b.bytes))
      : 1,
  );

  const load = async () => {
    loading = true;
    error = "";
    try {
      report = await get_api<ReclaimReport>("/api/reports/reclaim");
    } catch (e: any) {
      error = e.message ?? "Failed to load reports.";
    } finally {
      loading = false;
    }
  };

  onMount(load);
</script>

<div class="p-2.5 md:p-8 max-w-7xl mx-auto space-y-6">
  <div class="flex items-center gap-3">
    <div
      class="size-10 rounded-lg bg-primary/15 text-primary flex items-center justify-center shrink-0"
    >
      <ChartLine class="size-5" />
    </div>
    <div>
      <h1 class="text-3xl font-bold text-foreground">Reports</h1>
      <p class="text-muted-foreground">
        How much disk space you've reclaimed — and where it came from.
      </p>
    </div>
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
      <p class="mt-4">Loading reports...</p>
    </div>
  {:else if report}
    <!-- KPI cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div
        class="bg-gradient-to-br from-primary/15 via-card to-card rounded-lg border border-primary/40
          p-5"
      >
        <p class="text-xs uppercase tracking-wider text-muted-foreground">
          Total reclaimed
        </p>
        <p class="text-3xl font-bold text-primary mt-2">
          {formatBytes(report.total_bytes)}
        </p>
        <p class="text-xs text-muted-foreground mt-2">
          {report.total_events.toLocaleString()}
          {report.total_events === 1 ? "file" : "files"} deleted
        </p>
      </div>
      <div class="bg-card rounded-lg border border-border p-5">
        <p class="text-xs uppercase tracking-wider text-muted-foreground">
          Last 30 days
        </p>
        <p class="text-3xl font-bold text-foreground mt-2">
          {formatBytes(report.bytes_last_30d)}
        </p>
      </div>
      <div class="bg-card rounded-lg border border-border p-5">
        <p class="text-xs uppercase tracking-wider text-muted-foreground">
          Last 7 days
        </p>
        <p class="text-3xl font-bold text-foreground mt-2">
          {formatBytes(report.bytes_last_7d)}
        </p>
      </div>
      <div class="bg-card rounded-lg border border-border p-5">
        <p class="text-xs uppercase tracking-wider text-muted-foreground">
          Avg per file
        </p>
        <p class="text-3xl font-bold text-foreground mt-2">
          {report.total_events > 0
            ? formatBytes(Math.round(report.total_bytes / report.total_events))
            : "—"}
        </p>
      </div>
    </div>

    <!-- source breakdown -->
    <div class="bg-card rounded-lg border border-border p-6">
      <h2 class="text-lg font-semibold text-foreground mb-4">By source</h2>
      {#if report.total_events === 0}
        <p class="text-muted-foreground text-sm">
          No reclaim events yet. Run a scan and delete some candidates to see
          numbers here.
        </p>
      {:else}
        <div class="space-y-3">
          {#each sourceBreakdown as row (row.key)}
            <div>
              <div class="flex items-center justify-between gap-3 text-sm">
                <div class="flex items-center gap-2">
                  <span
                    class="size-7 rounded-md {row.meta.tint} flex items-center
                      justify-center shrink-0"
                  >
                    <row.meta.icon class="size-3.5" />
                  </span>
                  <span class="font-medium text-foreground"
                    >{row.meta.label}</span
                  >
                  <span class="text-muted-foreground text-xs">
                    · {row.count.toLocaleString()}
                    {row.count === 1 ? "file" : "files"}
                  </span>
                </div>
                <span class="font-mono text-foreground"
                  >{formatBytes(row.bytes)}</span
                >
              </div>
              <div
                class="mt-1.5 h-2 rounded-full bg-muted overflow-hidden"
              >
                <div
                  class="h-full {row.meta.bar} transition-[width] duration-500"
                  style="width: {row.pct}%"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- monthly histogram -->
    <div class="bg-card rounded-lg border border-border p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-foreground">Last 12 months</h2>
        <p class="text-xs text-muted-foreground">bytes reclaimed per month</p>
      </div>
      <div class="flex items-end gap-1.5 h-40">
        {#each report.monthly_histogram as bucket (bucket.month)}
          {@const pct = (bucket.bytes / histogramMax) * 100}
          <div class="flex-1 flex flex-col items-center gap-1.5 h-full group">
            <div
              class="flex-1 w-full flex items-end relative"
              title={`${formatMonth(bucket.month)}: ${formatBytes(bucket.bytes)}`}
            >
              <div
                class="w-full rounded-t {bucket.bytes > 0
                  ? 'bg-primary/70 group-hover:bg-primary'
                  : 'bg-muted'} transition-colors"
                style="height: {Math.max(bucket.bytes > 0 ? 4 : 2, pct)}%"
              ></div>
              {#if bucket.bytes > 0}
                <span
                  class="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px]
                    font-mono text-muted-foreground opacity-0
                    group-hover:opacity-100 whitespace-nowrap
                    bg-popover border border-border rounded px-1.5 py-0.5
                    pointer-events-none"
                >
                  {formatBytes(bucket.bytes)}
                </span>
              {/if}
            </div>
            <span class="text-[10px] text-muted-foreground tabular-nums">
              {formatMonth(bucket.month)}
            </span>
          </div>
        {/each}
      </div>
    </div>

    <!-- recent events -->
    <div class="bg-card rounded-lg border border-border">
      <div class="p-6 pb-3">
        <h2 class="text-lg font-semibold text-foreground">Recent activity</h2>
        <p class="text-xs text-muted-foreground mt-1">
          Last {report.recent.length}
          {report.recent.length === 1 ? "file" : "files"} reclaimed.
        </p>
      </div>
      {#if report.recent.length === 0}
        <p class="px-6 pb-6 text-sm text-muted-foreground">
          Nothing reclaimed yet.
        </p>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase text-muted-foreground border-y border-border">
                <th class="px-6 py-2 font-medium">Title</th>
                <th class="px-4 py-2 font-medium">Source</th>
                <th class="px-4 py-2 font-medium">Size</th>
                <th class="px-4 py-2 font-medium">By</th>
                <th class="px-6 py-2 font-medium text-right">When</th>
              </tr>
            </thead>
            <tbody>
              {#each report.recent as event (event.id)}
                {@const meta = metaFor(event.source)}
                <tr class="border-b border-border last:border-0 hover:bg-accent/20">
                  <td class="px-6 py-3">
                    <div class="flex items-center gap-2">
                      <span class="text-muted-foreground shrink-0">
                        {#if event.media_type === MediaType.Movie}
                          <ClapperBoard class="size-4" />
                        {:else}
                          <Tv class="size-4" />
                        {/if}
                      </span>
                      <span class="font-medium text-foreground truncate">
                        {event.media_title}
                      </span>
                      {#if event.media_year}
                        <span class="text-xs text-muted-foreground">
                          ({event.media_year})
                        </span>
                      {/if}
                    </div>
                    {#if event.notes}
                      <p class="text-xs text-muted-foreground mt-0.5 truncate">
                        {event.notes}
                      </p>
                    {/if}
                  </td>
                  <td class="px-4 py-3">
                    <span
                      class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md {meta.tint}
                        text-xs font-medium"
                    >
                      <meta.icon class="size-3" />
                      {meta.label}
                    </span>
                  </td>
                  <td class="px-4 py-3 font-mono text-foreground tabular-nums">
                    {formatSizeToGB(event.bytes_reclaimed)}
                  </td>
                  <td class="px-4 py-3 text-muted-foreground">
                    {event.triggered_by_username ?? "System"}
                  </td>
                  <td
                    class="px-6 py-3 text-right text-muted-foreground whitespace-nowrap"
                  >
                    {formatDistanceToNow(event.created_at)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>
