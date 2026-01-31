<script lang="ts">
  interface Props {
    tabLabel: string;
    enabled: boolean;
    baseUrl: string;
    apiKey: string;
    baseUrlPlaceholder?: string;
    onchange?: (event: CustomEvent) => void;
  }

  let {
    tabLabel,
    enabled,
    baseUrl,
    apiKey,
    baseUrlPlaceholder,
    onchange,
  }: Props = $props();

  function dispatchChange(field: string, value: any) {
    if (onchange) {
      onchange(new CustomEvent("change", { detail: { field, value } }));
    }
  }
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-xl font-semibold text-foreground">
      {tabLabel} Configuration
    </h2>
    <label class="flex items-center gap-2 cursor-pointer">
      <span class="text-sm text-foreground">Enable</span>
      <input
        type="checkbox"
        checked={enabled}
        onchange={(e) => dispatchChange("enabled", e.currentTarget.checked)}
        class="w-5 h-5 rounded bg-gray-800 border-gray-700 text-primary-600
                focus:ring-primary-500 focus:ring-offset-gray-900 cursor-pointer"
      />
    </label>
  </div>

  <div>
    <label for="baseUrl" class="block text-sm font-medium text-foreground mb-2"
      >Base URL</label
    >
    <input
      type="url"
      name="baseUrl"
      value={baseUrl}
      oninput={(e) => dispatchChange("baseUrl", e.currentTarget.value)}
      placeholder={baseUrlPlaceholder || "http://localhost:8096"}
      class="w-full px-4 py-2 bg-background border border-input rounded-lg text-foreground
                  placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring
                  focus:border-transparent"
    />
    <p class="mt-1 text-xs text-muted-foreground">
      The URL where your {tabLabel} instance is running
    </p>
  </div>

  <div>
    <label for="apiKey" class="block text-sm font-medium text-foreground mb-2"
      >API Key</label
    >
    <input
      type="password"
      name="apiKey"
      value={apiKey}
      oninput={(e) => dispatchChange("apiKey", e.currentTarget.value)}
      placeholder="Enter your API key"
      class="w-full px-4 py-2 bg-background border border-input rounded-lg text-foreground
                  placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring
                  focus:border-transparent"
    />
    <p class="mt-1 text-xs text-muted-foreground">
      Your {tabLabel} API key for authentication
    </p>
  </div>
</div>
