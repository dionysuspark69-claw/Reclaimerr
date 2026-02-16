<script lang="ts">
  import { onMount } from "svelte";
  import { get_api, post_api } from "$lib/api";
  import ErrorBox from "$lib/components/ErrorBox.svelte";
  import Spinner from "$lib/components/ui/spinner.svelte";
  import { Button } from "$lib/components/ui/button/index.js";
  import { toast } from "svelte-sonner";
  import type { UserProfile } from "$lib/types/shared";
  import Save from "@lucide/svelte/icons/save";
  import Pencil from "@lucide/svelte/icons/pencil";

  let loading = $state(false);
  let profile: UserProfile | null = $state(null);

  onMount(() => {
    // loadProfile();
  });
</script>

<div class="p-8">
  <div class="max-w-7xl mx-auto">
    <!-- header -->
    <div class="mb-2">
      <h1 class="text-3xl font-bold text-foreground mb-2">
        Reclaim Candidates
      </h1>
    </div>

    <!-- <ErrorBox error={profileError} /> -->

    {#if loading}
      <!-- <div class="p-8 text-center text-muted-foreground">
        <Spinner size="lg" class="text-primary" />
        <p class="mt-4">Loading profile...</p>
      </div> -->
    {:else if profile}
      PLACEHOLDER
    {/if}
  </div>
</div>
