<script lang="ts">
  let className: string = "";
  export { className as class };
  export let style: string = "";
</script>

<!--
  Original Tdarr branding is a stylized "T" over stacked drives. We render a
  non-branded, distinct icon so the settings entry is visually on-par with
  Radarr/Sonarr/Seerr/Tautulli SVGs and unmissable.
-->
<svg
  class={className}
  {style}
  width="24"
  height="24"
  viewBox="0 0 24 24"
  fill="none"
  xmlns="http://www.w3.org/2000/svg"
>
  <rect x="3" y="4" width="18" height="5" rx="1" fill="#7c4dff" />
  <rect x="3" y="10.5" width="18" height="5" rx="1" fill="#6639e5" />
  <rect x="3" y="17" width="18" height="3" rx="1" fill="#4b25b8" />
  <circle cx="6.5" cy="6.5" r="0.9" fill="#ffffff" />
  <circle cx="6.5" cy="13" r="0.9" fill="#ffffff" />
  <path
    d="M8 13h7M8 6.5h7"
    stroke="#ffffff"
    stroke-width="1"
    stroke-linecap="round"
  />
</svg>
