<template>
  <div class="space-y-3 border-t border-outline-gray-1 pt-3">
    <div class="flex items-center justify-between gap-2">
      <div class="text-xs font-medium text-ink-gray-6">
        {{ __("Suggested next steps") }}
      </div>
      <span
        class="inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium bg-surface-gray-2 text-ink-gray-8"
      >
        {{ branchLabel }}
      </span>
    </div>

    <!-- Auto-handle branch -->
    <div
      v-if="branch === 'auto_handle'"
      class="rounded border border-outline-gray-2 bg-surface-gray-1 p-3 space-y-2"
    >
      <p class="text-sm font-medium text-ink-gray-8">
        {{ plan?.title || __("Suitable for auto-handling") }}
      </p>
      <p class="text-xs text-ink-gray-6">
        {{
          __(
            "Suggestion / simulation only. No real password reset, refund, email, or script will be executed."
          )
        }}
      </p>
      <ol
        v-if="plan?.steps?.length"
        class="list-decimal pl-4 space-y-1 text-sm text-ink-gray-7"
      >
        <li v-for="(step, i) in plan.steps" :key="i">{{ step }}</li>
      </ol>
      <div class="flex flex-wrap gap-2 pt-1">
        <Button
          size="sm"
          variant="subtle"
          :label="__('Simulate auto-handle')"
          :loading="simulating"
          :disabled="readonly"
          @click="$emit('simulate')"
        />
      </div>
      <div
        v-if="simulation"
        class="rounded bg-surface-white border border-outline-gray-2 p-2 text-xs text-ink-gray-7 space-y-1"
      >
        <p class="font-medium text-ink-gray-8">
          {{ __("Simulation result") }}
        </p>
        <p>
          {{
            simulation.simulated_result?.message ||
            simulation.note ||
            __("Simulated successfully")
          }}
        </p>
        <p class="text-ink-gray-5">
          {{ __("Side effects") }}:
          {{ simulation.side_effects ? __("Yes") : __("None") }}
        </p>
      </div>
    </div>

    <!-- Missing info / handoff / manual -->
    <div
      v-else
      class="rounded border border-outline-gray-2 bg-surface-gray-1 p-3 space-y-2"
    >
      <p class="text-sm font-medium text-ink-gray-8">
        {{
          branch === "missing_info"
            ? __("Information needed")
            : __("Hand off to human agent")
        }}
      </p>
      <p v-if="reason" class="text-xs text-ink-gray-6">{{ reason }}</p>

      <div v-if="missingList.length" class="space-y-1">
        <p class="text-xs font-medium text-ink-gray-6">
          {{ __("Missing information") }}
        </p>
        <ul class="space-y-1">
          <li
            v-for="(item, idx) in missingList"
            :key="idx"
            class="text-sm text-ink-gray-7 flex gap-2"
          >
            <span>•</span>
            <span>
              {{ item.label || item.field || item }}
              <span v-if="item.reason" class="text-xs text-ink-gray-5">
                — {{ item.reason }}
              </span>
            </span>
          </li>
        </ul>
      </div>

      <div class="text-xs text-ink-gray-6 space-y-0.5">
        <p v-if="suggestedRole">
          {{ __("Suggested role") }}: {{ suggestedRole }}
        </p>
        <p v-if="suggestedTeam">
          {{ __("Suggested team") }}: {{ suggestedTeam }}
        </p>
      </div>

      <p class="text-xs text-ink-gray-5">
        {{
          __(
            "Re-analyze after the customer replies with more details. Confirming AI suggestions does not auto-close the ticket."
          )
        }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import type {
  AIAutoHandlePlan,
  AIBranch,
  AIMissingInfoItem,
} from "@/types/ai";
import { Button } from "frappe-ui";
import { computed } from "vue";

const props = defineProps<{
  branchInfo?: AIBranch | null;
  plan?: AIAutoHandlePlan | null;
  missingInfo?: Array<AIMissingInfoItem | string>;
  reason?: string | null;
  suggestedRole?: string | null;
  suggestedTeam?: string | null;
  simulation?: Record<string, any> | null;
  simulating?: boolean;
  readonly?: boolean;
}>();

defineEmits<{
  (e: "simulate"): void;
}>();

const branch = computed(() => props.branchInfo?.branch || "manual");
const branchLabel = computed(
  () => props.branchInfo?.label || props.branchInfo?.branch || __("Manual")
);
const missingList = computed(() => props.missingInfo || []);
</script>
