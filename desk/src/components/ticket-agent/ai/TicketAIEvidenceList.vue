<template>
  <div class="space-y-2">
    <div class="text-xs font-medium text-ink-gray-6">{{ __("Evidence") }}</div>
    <div v-if="!items.length" class="text-sm text-ink-gray-5">
      {{ __("No evidence available") }}
    </div>
    <ul v-else class="space-y-2">
      <li
        v-for="(item, idx) in visibleItems"
        :key="idx"
        class="rounded border border-outline-gray-2 bg-surface-gray-1 p-2"
      >
        <p class="text-sm text-ink-gray-8">{{ item.claim || __("Evidence") }}</p>
        <p
          v-if="item.quote"
          class="mt-1 text-xs text-ink-gray-6 italic border-l-2 border-outline-gray-3 pl-2"
        >
          “{{ item.quote }}”
        </p>
        <p class="mt-1 text-xs text-ink-gray-5">
          <span v-if="item.source">{{ item.source }}</span>
          <span v-if="item.rule"> · {{ item.rule }}</span>
        </p>
      </li>
    </ul>
    <button
      v-if="items.length > limit"
      type="button"
      class="text-xs text-ink-gray-7 underline"
      @click="expanded = !expanded"
    >
      {{ expanded ? __("Show less") : __("Show more") }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import type { AIEvidenceItem } from "@/types/ai";
import { computed, ref } from "vue";

const props = withDefaults(
  defineProps<{
    items?: AIEvidenceItem[];
    limit?: number;
  }>(),
  {
    items: () => [],
    limit: 3,
  }
);

const expanded = ref(false);
const visibleItems = computed(() =>
  expanded.value ? props.items : props.items.slice(0, props.limit)
);
</script>
