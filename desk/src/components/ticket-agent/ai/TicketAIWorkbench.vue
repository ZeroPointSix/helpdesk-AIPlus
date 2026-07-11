<template>
  <div class="px-4 pb-3">
    <Section :label="__('AI Workbench')" v-model:opened="opened">
      <template #header="{ opened: isOpen, toggle }">
        <div
          class="flex gap-2.5 items-center justify-between sticky top-0 bg-surface-white z-10 py-3 cursor-pointer"
          @click="toggle"
        >
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-ink-gray-8 font-semibold text-base select-none">
              {{ __("AI Workbench") }}
            </span>
            <TicketAIStatusBadge
              v-if="analysis"
              :status="analysis.status"
              :source="analysis.source"
              :confidence="analysis.confidence"
            />
          </div>
          <LucideChevronRight
            class="size-4 text-ink-gray-6 shrink-0"
            :class="{ 'rotate-90': isOpen }"
          />
        </div>
      </template>

      <div class="space-y-3 pb-2">
        <!-- Empty -->
        <div v-if="uiPhase === 'empty'" class="space-y-3">
          <p class="text-sm text-ink-gray-6">
            {{
              __(
                "No AI analysis yet. Run AI analysis to get category, priority, summary and evidence."
              )
            }}
          </p>
          <Button
            variant="solid"
            :label="__('AI Analysis')"
            :loading="loading"
            @click="runAnalyze"
          />
        </div>

        <!-- Loading -->
        <div
          v-else-if="uiPhase === 'loading'"
          class="flex items-center gap-2 text-sm text-ink-gray-6 py-2"
        >
          <LoadingIndicator class="w-4 h-4" />
          <span>{{ __("Analyzing ticket...") }}</span>
        </div>

        <!-- Error / Failed -->
        <div
          v-else-if="uiPhase === 'error' || uiPhase === 'failed'"
          class="space-y-2"
        >
          <p class="text-sm text-ink-gray-7">
            {{
              analysis?.error_message ||
              __("Analysis failed. You can retry safely.")
            }}
          </p>
          <Button
            variant="subtle"
            :label="__('Retry')"
            :loading="loading"
            @click="runAnalyze"
          />
        </div>

        <!-- Result / Confirmed / Rejected -->
        <div v-else class="space-y-3">
          <TicketAIStatusBadge
            :status="analysis?.status"
            :source="analysis?.source"
            :confidence="analysis?.confidence"
          />

          <p
            v-if="analysis?.status === 'Rejected' && analysis.rejection_reason"
            class="text-xs text-ink-gray-6"
          >
            {{ __("Rejection reason") }}: {{ analysis.rejection_reason }}
          </p>
          <p
            v-if="analysis?.status === 'Confirmed' && analysis.confirmed_by"
            class="text-xs text-ink-gray-6"
          >
            {{ __("Confirmed by") }}: {{ analysis.confirmed_by }}
            <span v-if="analysis.confirmed_at">
              · {{ analysis.confirmed_at }}
            </span>
          </p>

          <TicketAIResultForm
            :draft="draft"
            :editable="isEditable"
            :analysis="analysis"
            :original-result="originalResult"
          />

          <TicketAIEvidenceList :items="evidence" />

          <TicketAIFollowup
            :branch-info="analysis?.branch"
            :plan="autoHandlePlan"
            :missing-info="missingInfo"
            :reason="analysis?.handoff_reason || analysis?.branch?.reason"
            :suggested-role="analysis?.suggested_role || draft.suggested_role"
            :suggested-team="analysis?.suggested_team || draft.suggested_team"
            :simulation="simulation"
            :simulating="Boolean(loading && simulation === null)"
            :readonly="analysis?.status !== 'Completed'"
            @simulate="runSimulation"
          />

          <!-- Actions -->
          <div class="flex flex-wrap gap-2 pt-1">
            <Button
              v-if="canEdit && !editing"
              size="sm"
              variant="subtle"
              :label="__('Edit')"
              @click="startEdit"
            />
            <Button
              v-if="editing"
              size="sm"
              variant="subtle"
              :label="__('Save changes')"
              :loading="loading"
              :disabled="!isDirty"
              @click="saveDraft"
            />
            <Button
              v-if="editing"
              size="sm"
              variant="ghost"
              :label="__('Cancel')"
              @click="cancelEdit"
            />
            <Button
              v-if="canConfirmOrReject"
              size="sm"
              variant="solid"
              :label="__('Confirm & Apply')"
              :loading="loading"
              @click="openConfirmPreview"
            />
            <Button
              v-if="canConfirmOrReject"
              size="sm"
              variant="ghost"
              :label="__('Reject')"
              :loading="loading"
              @click="showReject = true"
            />
            <Button
              size="sm"
              variant="outline"
              :label="__('Re-analyze')"
              :loading="loading"
              @click="runAnalyze"
            />
          </div>

          <p class="text-[11px] text-ink-gray-5 leading-relaxed">
            {{
              __(
                "Confirming AI suggestions writes selected ticket fields only. Ticket status is not changed automatically. Auto-handle is suggestion/simulation only."
              )
            }}
          </p>
        </div>

        <!-- Confirm preview -->
        <div
          v-if="showConfirmPreview"
          class="rounded border border-outline-gray-2 bg-surface-gray-1 p-3 space-y-2"
        >
          <p class="text-sm font-medium text-ink-gray-8">
            {{ __("Preview write-back to ticket") }}
          </p>
          <label
            v-for="field in confirmFieldOptions"
            :key="field.value"
            class="flex items-center gap-2 text-sm text-ink-gray-7"
          >
            <input
              type="checkbox"
              class="rounded border-outline-gray-3"
              :value="field.value"
              v-model="applyFields"
            />
            <span>
              {{ field.label }}
              <span class="text-xs text-ink-gray-5">
                → {{ fieldPreview(field.value) }}
              </span>
            </span>
          </label>
          <div class="flex gap-2 pt-1">
            <Button
              size="sm"
              variant="solid"
              :label="__('Confirm adoption')"
              :loading="loading"
              @click="confirmAdoption"
            />
            <Button
              size="sm"
              variant="ghost"
              :label="__('Cancel')"
              @click="showConfirmPreview = false"
            />
          </div>
        </div>

        <!-- Reject reason -->
        <div
          v-if="showReject"
          class="rounded border border-outline-gray-2 bg-surface-gray-1 p-3 space-y-2"
        >
          <label class="block text-xs text-ink-gray-5">{{
            __("Rejection reason")
          }}</label>
          <TextInput
            v-model="rejectReason"
            :placeholder="__('Optional reason')"
          />
          <div class="flex gap-2">
            <Button
              size="sm"
              variant="solid"
              :label="__('Confirm reject')"
              :loading="loading"
              @click="
                () => {
                  rejectAnalysis();
                  showReject = false;
                }
              "
            />
            <Button
              size="sm"
              variant="ghost"
              :label="__('Cancel')"
              @click="showReject = false"
            />
          </div>
        </div>
      </div>
    </Section>
  </div>
</template>

<script setup lang="ts">
import Section from "@/components/Section.vue";
import { useTicketAI } from "@/composables/useTicketAI";
import { __ } from "@/translation";
import { Button, LoadingIndicator, TextInput } from "frappe-ui";
import { ref } from "vue";
import LucideChevronRight from "~icons/lucide/chevron-right";
import TicketAIEvidenceList from "./TicketAIEvidenceList.vue";
import TicketAIFollowup from "./TicketAIFollowup.vue";
import TicketAIResultForm from "./TicketAIResultForm.vue";
import TicketAIStatusBadge from "./TicketAIStatusBadge.vue";

const props = defineProps<{
  ticketId: string;
}>();

const opened = ref(true);
const showReject = ref(false);

const {
  analysis,
  draft,
  editing,
  loading,
  uiPhase,
  isEditable,
  canEdit,
  canConfirmOrReject,
  evidence,
  missingInfo,
  autoHandlePlan,
  originalResult,
  isDirty,
  applyFields,
  showConfirmPreview,
  simulation,
  rejectReason,
  runAnalyze,
  startEdit,
  cancelEdit,
  saveDraft,
  openConfirmPreview,
  confirmAdoption,
  rejectAnalysis,
  runSimulation,
} = useTicketAI(props.ticketId);

const confirmFieldOptions = [
  {
    value: "mapped_ticket_type",
    label: __("Ticket type"),
  },
  { value: "priority", label: __("Priority") },
  { value: "summary", label: __("Summary") },
  { value: "suggested_team", label: __("Team / agent group") },
  { value: "suggested_agent", label: __("Assign agent") },
];

function fieldPreview(field: string) {
  switch (field) {
    case "mapped_ticket_type":
      return draft.mapped_ticket_type || draft.category || "-";
    case "priority":
      return draft.priority || "-";
    case "summary":
      return (draft.summary || "-").slice(0, 40);
    case "suggested_team":
      return draft.suggested_team || "-";
    case "suggested_agent":
      return draft.suggested_agent || "-";
    default:
      return "-";
  }
}
</script>
