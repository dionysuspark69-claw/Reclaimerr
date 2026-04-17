<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { get_api, post_api } from "$lib/api";
  import ErrorBox from "$lib/components/error-box.svelte";
  import CompactPagination from "$lib/components/compact-pagination.svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { Input } from "$lib/components/ui/input/index.js";
  import * as Select from "$lib/components/ui/select/index.js";
  import * as AlertDialog from "$lib/components/ui/alert-dialog/index.js";
  import * as Tooltip from "$lib/components/ui/tooltip/index.js";
  import { auth } from "$lib/stores/auth";
  import { safeMode } from "$lib/stores/safe-mode";
  import { safeDelete } from "$lib/utils/safe-delete";
  import {
    BackgroundJobStatus,
    MediaType,
    UserRole,
    Permission,
    type DuplicateGroupEntry,
    type DuplicateCandidateEntry,
    type PaginatedDuplicatesResponse,
  } from "$lib/types/shared";
  import {
    createPerPageState,
    createFilterState,
    PER_PAGE_OPTIONS,
  } from "$lib/utils/pagination";
  import { formatDate } from "$lib/utils/date";
  import { toast } from "svelte-sonner";
  import Search from "@lucide/svelte/icons/search";
  import Trash from "@lucide/svelte/icons/trash";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Copy from "@lucide/svelte/icons/copy";
  import MediaTypeBadge from "$lib/components/requests/media-type-badge.svelte";
  import PosterThumb from "$lib/components/requests/poster-thumb.svelte";

  interface ResolveResponse {
    deleted: number;
    failed: number;
    groups_resolved: number;
  }

  let data = $state<PaginatedDuplicatesResponse | null>(null);
  let loading = $state(true);
  let error = $state("");
  let searchQuery = $state("");
  let scanning = $state(false);
  let scanStatus = $state<string>("");
  let scanPollTimer: ReturnType<typeof setTimeout> | null = null;

  const _sortByStore = createFilterState(
    "duplicates_sort_by",
    "reclaimable_size",
  );
  const _sortOrderStore = createFilterState("duplicates_sort_order", "desc");
  const _mediaTypeStore = createFilterState("duplicates_media_type", "all");
  let sortBy = $state(_sortByStore.getInitial());
  let sortOrder = $state(_sortOrderStore.getInitial());
  let mediaTypeFilter = $state(_mediaTypeStore.getInitial());
  let currentPage = $state(1);

  const _perPageStore = createPerPageState("duplicates_per_page");
  let perPage = $state(_perPageStore.getInitial());

  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let abortController: AbortController | null = null;
  let mounted = $state(false);

  let expandedGroups = $state<Set<number>>(new Set());
  let selectedGroups = $state<Set<number>>(new Set());

  let resolveDialogOpen = $state(false);
  let resolveTarget = $state<DuplicateGroupEntry | null>(null);
  let resolveSubmitting = $state(false);

  let bulkResolveDialogOpen = $state(false);
  let bulkResolveSubmitting = $state(false);

  const sortByOptions = [
    { value: "reclaimable_size", label: "Reclaimable Size" },
    { value: "total_size", label: "Total Size" },
    { value: "title", label: "Title" },
    { value: "created_at", label: "Date Found" },
  ];

  const groups = $derived(data?.items ?? []);

  const canDelete = $derived(
    $auth.user?.role === UserRole.Admin ||
      ($auth.user?.permissions ?? []).includes(Permission.ManageReclaim),
  );

  const totalReclaimableGb = $derived(
    data ? data.total_reclaimable_bytes / 1024 / 1024 / 1024 : 0,
  );

  const allGroupIds = $derived(groups.map((g) => g.id));
  const allPageSelected = $derived(
    allGroupIds.length > 0 &&
      allGroupIds.every((id) => selectedGroups.has(id)),
  );

  const selectedGroupEntries = $derived(
    groups.filter((g) => selectedGroups.has(g.id)),
  );

  const selectedReclaimableGb = $derived(
    selectedGroupEntries.reduce(
      (acc, g) => acc + g.reclaimable_size / 1024 / 1024 / 1024,
      0,
    ),
  );

  $effect(() => _sortByStore.save(sortBy));
  $effect(() => _sortOrderStore.save(sortOrder));
  $effect(() => _mediaTypeStore.save(mediaTypeFilter));

  $effect(() => {
    sortBy;
    sortOrder;
    mediaTypeFilter;
    perPage;
    if (mounted) loadDuplicates(1);
  });

  const loadDuplicates = async (page: number = currentPage) => {
    if (abortController) abortController.abort();
    abortController = new AbortController();
    const signal = abortController.signal;

    loading = true;
    error = "";
    currentPage = page;
    selectedGroups = new Set();
    expandedGroups = new Set();

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (searchQuery.trim()) params.append("search", searchQuery.trim());
      if (mediaTypeFilter !== "all")
        params.append("media_type", mediaTypeFilter);

      data = await get_api<PaginatedDuplicatesResponse>(
        `/api/media/duplicates?${params.toString()}`,
        signal,
      );
    } catch (e: any) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      error = e.message ?? "Failed to load duplicates.";
    } finally {
      if (!signal.aborted) loading = false;
    }
  };

  const handleSearch = (event: Event) => {
    searchQuery = (event.target as HTMLInputElement).value;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadDuplicates(1), 400);
  };

  interface ScanResponse {
    queued: boolean;
    job_id: number | null;
  }

  interface JobStatusResponse {
    id: number;
    status: BackgroundJobStatus;
    error_message: string | null;
  }

  const stopScanPolling = () => {
    if (scanPollTimer) {
      clearTimeout(scanPollTimer);
      scanPollTimer = null;
    }
  };

  const pollScanJob = async (jobId: number) => {
    try {
      const job = await get_api<JobStatusResponse>(
        `/api/tasks/background-jobs/${jobId}/status`,
      );

      if (job.status === BackgroundJobStatus.Completed) {
        scanning = false;
        scanStatus = "";
        stopScanPolling();
        toast.success("Duplicate scan complete.");
        await loadDuplicates(currentPage);
        return;
      }

      if (
        job.status === BackgroundJobStatus.Failed ||
        job.status === BackgroundJobStatus.Canceled
      ) {
        scanning = false;
        scanStatus = "";
        stopScanPolling();
        toast.error(
          job.error_message ??
            (job.status === BackgroundJobStatus.Canceled
              ? "Scan was canceled."
              : "Scan failed."),
        );
        return;
      }

      scanStatus =
        job.status === BackgroundJobStatus.Running ? "Scanning..." : "Queued...";
      scanPollTimer = setTimeout(() => pollScanJob(jobId), 2000);
    } catch (e: any) {
      // stop polling on transient error; user can re-scan manually.
      stopScanPolling();
      scanning = false;
      scanStatus = "";
      toast.error(e.message ?? "Lost track of the scan job.");
    }
  };

  const triggerScan = async () => {
    scanning = true;
    scanStatus = "Starting...";
    stopScanPolling();
    try {
      const resp = await post_api<ScanResponse>(
        "/api/media/scan-duplicates",
        {},
      );
      if (!resp.queued && resp.job_id === null) {
        toast.info("A duplicate scan is already running.");
        scanning = false;
        scanStatus = "";
        return;
      }
      if (resp.job_id === null) {
        // queued but no id returned — fall back to simple feedback.
        toast.success(
          "Duplicate scan queued — refresh the page in a moment to see results.",
        );
        scanning = false;
        scanStatus = "";
        return;
      }
      scanStatus = "Queued...";
      scanPollTimer = setTimeout(
        () => pollScanJob(resp.job_id as number),
        1500,
      );
    } catch (e: any) {
      toast.error(e.message ?? "Failed to start scan.");
      scanning = false;
      scanStatus = "";
    }
  };

  const toggleGroupExpand = (id: number) => {
    const next = new Set(expandedGroups);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expandedGroups = next;
  };

  const toggleGroupSelect = (id: number) => {
    const next = new Set(selectedGroups);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedGroups = next;
  };

  const toggleSelectAll = () => {
    if (allPageSelected) selectedGroups = new Set();
    else selectedGroups = new Set(allGroupIds);
  };

  const toggleKeep = async (
    group: DuplicateGroupEntry,
    cand: DuplicateCandidateEntry,
  ) => {
    if (!canDelete) return;
    // optimistic update
    const next = !cand.keep;
    cand.keep = next;
    // recompute reclaimable_size locally
    group.reclaimable_size = group.candidates
      .filter((c) => !c.keep)
      .reduce((acc, c) => acc + c.size, 0);
    try {
      await post_api("/api/media/toggle-duplicate-keep", {
        candidate_id: cand.id,
      });
    } catch (e: any) {
      // revert on failure
      cand.keep = !next;
      group.reclaimable_size = group.candidates
        .filter((c) => !c.keep)
        .reduce((acc, c) => acc + c.size, 0);
      toast.error(e.message ?? "Failed to update keep flag.");
    }
  };

  const openResolve = (group: DuplicateGroupEntry) => {
    resolveTarget = group;
    resolveDialogOpen = true;
  };

  const submitResolve = async () => {
    if (!resolveTarget) return;
    const target = resolveTarget;
    resolveSubmitting = true;
    resolveDialogOpen = false;

    await safeDelete({
      safeMode: $safeMode,
      label: target.title ?? "duplicate",
      action: async () => {
        const resp = await post_api<ResolveResponse>(
          "/api/media/duplicates/resolve",
          { group_ids: [target.id] },
        );
        if (resp.deleted > 0)
          toast.success(
            `Deleted ${resp.deleted} duplicate file${resp.deleted !== 1 ? "s" : ""}.`,
          );
        if (resp.failed > 0)
          toast.error(
            `${resp.failed} file${resp.failed !== 1 ? "s" : ""} could not be deleted.`,
          );
        if (resp.deleted > 0) await loadDuplicates(currentPage);
      },
    });

    resolveSubmitting = false;
    resolveTarget = null;
  };

  const submitBulkResolve = async () => {
    if (selectedGroupEntries.length === 0) return;
    const groups = selectedGroupEntries;
    bulkResolveSubmitting = true;
    bulkResolveDialogOpen = false;

    await safeDelete({
      safeMode: $safeMode,
      label: `${groups.length} duplicate group${groups.length !== 1 ? "s" : ""}`,
      action: async () => {
        const resp = await post_api<ResolveResponse>(
          "/api/media/duplicates/resolve",
          { group_ids: groups.map((g) => g.id) },
        );
        if (resp.deleted > 0)
          toast.success(
            `Resolved ${resp.groups_resolved} group${resp.groups_resolved !== 1 ? "s" : ""} - ` +
              `deleted ${resp.deleted} file${resp.deleted !== 1 ? "s" : ""}.`,
          );
        if (resp.failed > 0)
          toast.error(
            `${resp.failed} file${resp.failed !== 1 ? "s" : ""} failed to delete.`,
          );
        if (resp.deleted > 0) await loadDuplicates(currentPage);
      },
    });

    bulkResolveSubmitting = false;
    selectedGroups = new Set();
  };

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    if (bytes < 1024 * 1024 * 1024)
      return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  };

  const detectionLabel = (kind: string) => {
    if (kind === "cross_library") return "In multiple libraries";
    if (kind === "multi_version") return "Multiple copies";
    if (kind === "mixed") return "Multiple libraries + copies";
    return kind;
  };

  const detectionBadgeClass = (kind: string) => {
    if (kind === "cross_library") return "bg-blue-500/20 text-blue-400";
    if (kind === "multi_version") return "bg-amber-500/20 text-amber-400";
    if (kind === "mixed") return "bg-purple-500/20 text-purple-400";
    return "bg-muted text-muted-foreground";
  };

  onMount(async () => {
    mounted = true;
    await loadDuplicates();
  });

  onDestroy(() => {
    if (searchTimer) clearTimeout(searchTimer);
    if (abortController) abortController.abort();
    stopScanPolling();
  });
</script>

<!-- single-group resolve dialog -->
<AlertDialog.Root bind:open={resolveDialogOpen}>
  <AlertDialog.Content class="text-foreground">
    <AlertDialog.Header>
      <AlertDialog.Title>Resolve duplicate?</AlertDialog.Title>
      <AlertDialog.Description>
        {#if resolveTarget}
          This will permanently delete every copy of <strong
            >{resolveTarget.title ?? "this title"}</strong
          >
          that isn't marked "keep". Frees ~{formatBytes(
            resolveTarget.reclaimable_size,
          )}.
        {/if}
      </AlertDialog.Description>
    </AlertDialog.Header>
    <AlertDialog.Footer>
      <AlertDialog.Cancel disabled={resolveSubmitting}>Cancel</AlertDialog.Cancel
      >
      <AlertDialog.Action
        onclick={submitResolve}
        disabled={resolveSubmitting}
      >
        {resolveSubmitting ? "Deleting..." : "Delete duplicates"}
      </AlertDialog.Action>
    </AlertDialog.Footer>
  </AlertDialog.Content>
</AlertDialog.Root>

<!-- bulk resolve dialog -->
<AlertDialog.Root bind:open={bulkResolveDialogOpen}>
  <AlertDialog.Content class="text-foreground">
    <AlertDialog.Header>
      <AlertDialog.Title
        >Resolve {selectedGroupEntries.length} duplicate group{selectedGroupEntries.length !==
        1
          ? "s"
          : ""}?</AlertDialog.Title
      >
      <AlertDialog.Description>
        Permanently delete every non-kept copy in {selectedGroupEntries.length} group{selectedGroupEntries.length !==
        1
          ? "s"
          : ""}. Frees ~{selectedReclaimableGb.toFixed(2)} GB. Cannot be undone.
      </AlertDialog.Description>
    </AlertDialog.Header>
    <AlertDialog.Footer>
      <AlertDialog.Cancel disabled={bulkResolveSubmitting}
        >Cancel</AlertDialog.Cancel
      >
      <AlertDialog.Action
        onclick={submitBulkResolve}
        disabled={bulkResolveSubmitting}
      >
        {bulkResolveSubmitting
          ? "Deleting..."
          : `Delete ${selectedGroupEntries.length} group${selectedGroupEntries.length !== 1 ? "s" : ""}`}
      </AlertDialog.Action>
    </AlertDialog.Footer>
  </AlertDialog.Content>
</AlertDialog.Root>

<div class="p-2.5 md:p-8 max-w-7xl mx-auto space-y-4">
  <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
    <div class="space-y-2">
      <h1 class="text-3xl font-bold text-foreground flex items-center gap-2">
        <Copy class="size-7 text-primary" />
        Duplicates
      </h1>
      <p class="text-muted-foreground">
        Same title across multiple libraries or with multiple file versions.
        {#if data && data.total > 0}
          <span class="text-foreground font-medium"
            >{totalReclaimableGb.toFixed(2)} GB reclaimable</span
          >
          across {data.total} group{data.total !== 1 ? "s" : ""}.
        {/if}
      </p>
    </div>
    <Button
      variant="outline"
      onclick={triggerScan}
      disabled={scanning}
      class="cursor-pointer"
    >
      <RefreshCw class="size-4 {scanning ? 'animate-spin' : ''}" />
      {scanning ? (scanStatus || "Scanning...") : "Scan now"}
    </Button>
  </div>

  <!-- filters -->
  <div class="flex flex-col sm:flex-row gap-2">
    <div class="relative flex-1">
      <Search
        class="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground"
      />
      <Input
        type="text"
        placeholder="Search by title"
        value={searchQuery}
        oninput={handleSearch}
        class="pl-10 bg-card"
      />
    </div>

    <div class="flex flex-1 flex-col gap-2 sm:flex-row">
      <div class="flex flex-1 gap-2">
        <Select.Root type="single" bind:value={sortBy}>
          <Select.Trigger class="flex-1 bg-card text-card-foreground">
            {sortByOptions.find((o) => o.value === sortBy)?.label}
          </Select.Trigger>
          <Select.Content class="bg-card">
            {#each sortByOptions as opt}
              <Select.Item
                value={opt.value}
                label={opt.label}
                class="text-card-foreground">{opt.label}</Select.Item
              >
            {/each}
          </Select.Content>
        </Select.Root>

        <Select.Root type="single" bind:value={sortOrder}>
          <Select.Trigger class="flex-1 bg-card text-card-foreground">
            {sortOrder === "asc" ? "Ascending" : "Descending"}
          </Select.Trigger>
          <Select.Content class="bg-card">
            <Select.Item
              value="asc"
              label="Ascending"
              class="text-card-foreground">Ascending</Select.Item
            >
            <Select.Item
              value="desc"
              label="Descending"
              class="text-card-foreground">Descending</Select.Item
            >
          </Select.Content>
        </Select.Root>
      </div>

      <div class="flex flex-1 gap-2">
        <Select.Root type="single" bind:value={mediaTypeFilter}>
          <Select.Trigger class="flex-1 bg-card text-card-foreground">
            {mediaTypeFilter === "all"
              ? "All Media"
              : mediaTypeFilter === MediaType.Movie
                ? "Movies"
                : "Series"}
          </Select.Trigger>
          <Select.Content class="bg-card">
            <Select.Item
              value="all"
              label="All Media"
              class="text-card-foreground">All Media</Select.Item
            >
            <Select.Item
              value={MediaType.Movie}
              label="Movies"
              class="text-card-foreground">Movies</Select.Item
            >
            <Select.Item
              value={MediaType.Series}
              label="Series"
              class="text-card-foreground">Series</Select.Item
            >
          </Select.Content>
        </Select.Root>

        <Select.Root
          type="single"
          value={perPage.toString()}
          onValueChange={(v) => {
            const n = parseInt(v, 10);
            if (!isNaN(n)) {
              perPage = n;
              _perPageStore.save(n);
            }
          }}
        >
          <Select.Trigger class="flex-1 bg-card text-card-foreground">
            {perPage} / page
          </Select.Trigger>
          <Select.Content class="bg-card">
            {#each PER_PAGE_OPTIONS as opt}
              <Select.Item
                value={opt.toString()}
                label={`${opt} / page`}
                class="text-card-foreground"
              >
                {opt} / page
              </Select.Item>
            {/each}
          </Select.Content>
        </Select.Root>
      </div>
    </div>
  </div>

  <!-- bulk action bar -->
  {#if canDelete && selectedGroups.size > 0}
    <div
      class="flex items-center justify-between gap-4 px-4 py-3 bg-primary/10 border border-primary/30
        rounded-lg"
    >
      <span class="text-sm text-foreground font-medium">
        {selectedGroups.size} group{selectedGroups.size !== 1 ? "s" : ""} selected
        <span class="text-muted-foreground font-normal">
          - frees {selectedReclaimableGb.toFixed(2)} GB
        </span>
      </span>
      <div class="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          class="cursor-pointer"
          onclick={() => (selectedGroups = new Set())}
        >
          Clear
        </Button>
        <Button
          size="sm"
          class="cursor-pointer bg-destructive/80 hover:bg-destructive/60"
          onclick={() => (bulkResolveDialogOpen = true)}
        >
          <Trash class="size-4" />
          Delete {selectedGroups.size}
        </Button>
      </div>
    </div>
  {/if}

  <ErrorBox {error} />

  <div class="bg-card rounded-lg border border-border overflow-x-auto">
    {#if loading}
      <div class="p-8 text-center text-muted-foreground">
        <div
          class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary
            border-r-transparent"
        ></div>
        <p class="mt-4">Loading duplicates...</p>
      </div>
    {:else if groups.length === 0}
      <div class="p-8 text-center text-muted-foreground space-y-3">
        <p>No duplicate groups found.</p>
        <p class="text-sm">
          Run a scan to check your library for duplicates across libraries and
          file versions.
        </p>
        <Button
          variant="outline"
          onclick={triggerScan}
          disabled={scanning}
          class="cursor-pointer"
        >
          <RefreshCw class="size-4 {scanning ? 'animate-spin' : ''}" />
          {scanning ? "Scanning..." : "Run scan"}
        </Button>
      </div>
    {:else}
      <table class="w-full">
        <thead class="bg-muted/50">
          <tr>
            {#if canDelete}
              <th class="px-4 py-3 w-10">
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  onchange={toggleSelectAll}
                  class="cursor-pointer accent-primary"
                />
              </th>
            {/if}
            <th
              class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >Title</th
            >
            <th
              class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >Type</th
            >
            <th
              class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >Copies</th
            >
            <th
              class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >Reclaimable</th
            >
            <th
              class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >Found</th
            >
            <th
              class="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider"
              >Actions</th
            >
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          {#each groups as group (group.id)}
            {@const expanded = expandedGroups.has(group.id)}
            {@const selected = selectedGroups.has(group.id)}
            <tr
              class="hover:bg-muted/30 transition-colors cursor-pointer {selected
                ? 'bg-primary/5'
                : ''}"
              onclick={() => toggleGroupExpand(group.id)}
            >
              {#if canDelete}
                <td
                  class="px-4 py-4 w-10"
                  onclick={(e) => e.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onchange={() => toggleGroupSelect(group.id)}
                    class="cursor-pointer accent-primary"
                  />
                </td>
              {/if}
              <td class="px-6 py-4">
                <div class="flex gap-4 items-center">
                  <div class="flex flex-col items-center w-max gap-1">
                    <PosterThumb
                      mediaType={group.media_type}
                      posterUrl={group.poster_url}
                    />
                    <MediaTypeBadge mediaType={group.media_type} />
                  </div>
                  <div class="text-sm font-medium text-foreground">
                    {group.title ?? "Unknown title"}
                    {#if group.year}
                      <span class="text-muted-foreground">({group.year})</span>
                    {/if}
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  class="text-xs px-2 py-1 rounded-full {detectionBadgeClass(
                    group.detection_kind,
                  )}"
                >
                  {detectionLabel(group.detection_kind)}
                </span>
              </td>
              <td class="px-6 py-4 text-sm text-foreground whitespace-nowrap">
                {group.candidate_count}
              </td>
              <td class="px-6 py-4 text-sm whitespace-nowrap">
                <span class="text-green-500 font-medium">
                  {formatBytes(group.reclaimable_size)}
                </span>
                <span class="text-muted-foreground text-xs ml-1">
                  / {formatBytes(group.total_size)}
                </span>
              </td>
              <td
                class="px-6 py-4 text-sm text-muted-foreground whitespace-nowrap"
              >
                {formatDate(group.created_at)}
              </td>
              <td
                class="px-6 py-4 text-right whitespace-nowrap"
                onclick={(e) => e.stopPropagation()}
              >
                <div class="flex gap-2 justify-end items-center">
                  {#if canDelete}
                    <Tooltip.Root>
                      <Tooltip.Trigger>
                        <Button
                          size="icon"
                          class="cursor-pointer rounded-full bg-destructive/80 hover:bg-destructive/60"
                          onclick={() => openResolve(group)}
                        >
                          <Trash class="size-4" />
                        </Button>
                      </Tooltip.Trigger>
                      <Tooltip.Content>
                        <p>Delete non-kept copies</p>
                      </Tooltip.Content>
                    </Tooltip.Root>
                  {/if}
                  <ChevronRight
                    class="size-4 text-muted-foreground transition-transform duration-200 {expanded
                      ? 'rotate-90'
                      : ''}"
                  />
                </div>
              </td>
            </tr>

            {#if expanded}
              {#each group.candidates as cand (cand.id)}
                <tr
                  class="bg-muted/20 border-l-2 transition-colors {cand.keep
                    ? 'border-l-green-500/60'
                    : 'border-l-destructive/40'}"
                >
                  {#if canDelete}
                    <td class="px-4 py-3 w-10 pl-8">
                      <input
                        type="checkbox"
                        checked={cand.keep}
                        onchange={() => toggleKeep(group, cand)}
                        class="cursor-pointer accent-green-500"
                        title="Keep this copy"
                      />
                    </td>
                  {/if}
                  <td class="px-6 py-3 pl-14" colspan={2}>
                    <div class="text-sm">
                      <div class="font-medium text-foreground flex gap-2 items-center">
                        <span class="capitalize">{cand.service}</span>
                        {#if cand.library_name}
                          <span class="text-muted-foreground">·</span>
                          <span class="text-muted-foreground"
                            >{cand.library_name}</span
                          >
                        {/if}
                        {#if cand.keep}
                          <span
                            class="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400"
                            >KEEP</span
                          >
                        {:else}
                          <span
                            class="text-xs px-2 py-0.5 rounded-full bg-destructive/20 text-destructive"
                            >DELETE</span
                          >
                        {/if}
                      </div>
                      {#if cand.path}
                        <div
                          class="text-xs text-muted-foreground font-mono truncate max-w-md mt-0.5"
                          title={cand.path}
                        >
                          {cand.path}
                        </div>
                      {/if}
                    </div>
                  </td>
                  <td class="px-6 py-3 text-sm text-muted-foreground whitespace-nowrap">
                    {cand.resolution ?? "?"}
                    {#if cand.container}
                      <span class="text-xs ml-1">· {cand.container}</span>
                    {/if}
                  </td>
                  <td class="px-6 py-3 text-sm text-foreground whitespace-nowrap">
                    {formatBytes(cand.size)}
                  </td>
                  <td class="px-6 py-3" colspan={2}></td>
                </tr>
              {/each}
            {/if}
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  {#if !loading && groups.length !== 0 && data && data.total_pages > 1}
    <div
      class="flex flex-wrap justify-center gap-2 md:flex-nowrap md:justify-between items-center"
    >
      <p class="text-sm text-muted-foreground">
        Showing {(data.page - 1) * data.per_page + 1} to {Math.min(
          data.page * data.per_page,
          data.total,
        )} of {data.total} duplicate groups
      </p>
      <CompactPagination
        currentPage={data.page}
        totalPages={data.total_pages}
        maxVisiblePages={3}
        onPageChange={loadDuplicates}
      />
    </div>
  {/if}
</div>
