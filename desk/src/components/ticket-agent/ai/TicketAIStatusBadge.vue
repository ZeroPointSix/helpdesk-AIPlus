<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <span
      class="inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium"
      :class="statusClass"
    >
      {{ statusLabel }}
    </span>
    <span
      v-if="source"
      class="inline-flex items-center rounded-sm px-2 py-0.5 text-xs text-ink-gray-6 bg-surface-gray-2"
    >
      {{ source }}
    </span>
    <span
      v-if="confidence != null"
      class="inline-flex items-center rounded-sm px-2 py-0.5 text-xs text-ink-gray-7 bg-surface-gray-1"
    >
      {{ __("Confidence") }}: {{ confidencePercent }}%
    </span>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import { computed } from "vue";

const props = defineProps<{
  status?: string;
  source?: string;
  confidence?: number | null;
}>();

const confidencePercent = computed(() => {
  if (props.confidence == null || Number.isNaN(Number(props.confidence))) {
    return "-";
  }
  return Math.round(Number(props.confidence) * 100);
});

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    Pending: __("Pending"),
    Completed: __("Completed"),
    Failed: __("Failed"),
    Confirmed: __("Confirmed"),
    Rejected: __("Rejected"),
  };
  return map[props.status || ""] || props.status || "-";
});

const statusClass = computed(() => {
  switch (props.status) {
    case "Completed":
      return "bg-surface-gray-2 text-ink-gray-8";
    case "Confirmed":
      return "bg-surface-gray-3 text-ink-gray-9";
    case "Rejected":
      return "bg-surface-gray-2 text-ink-gray-6";
    case "Failed":
      return "bg-surface-gray-2 text-ink-gray-7";
    case "Pending":
      return "bg-surface-gray-1 text-ink-gray-6";
    default:
      return "bg-surface-gray-1 text-ink-gray-6";
  }
});
</script>
