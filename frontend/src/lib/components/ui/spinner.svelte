<script lang="ts">
  import { cn } from "$lib/utils";

  let className: string | undefined = undefined;
  export { className as class };
  export let size: "sm" | "md" | "lg" = "md";

  const sizes = {
    sm: "h-4 w-4 border-2",
    md: "h-6 w-6 border-2",
    lg: "h-8 w-8 border-3",
  };
</script>

<div
  class={cn(
    "inline-block animate-spin rounded-full border-solid border-current border-r-transparent motion-reduce:animate-[spin_1.5s_linear_infinite]",
    sizes[size],
    className,
  )}
  role="status"
  aria-label="Loading"
>
  <span class="sr-only">Loading...</span>
</div>
