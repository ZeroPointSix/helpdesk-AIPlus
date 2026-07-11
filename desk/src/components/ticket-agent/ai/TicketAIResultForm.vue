<template>
  <div class="space-y-3">
    <div class="grid grid-cols-1 gap-2">
      <div>
        <label class="block text-xs text-ink-gray-5 mb-1">{{
          __("Category")
        }}</label>
        <TextInput
          v-if="editable"
          v-model="draft.category"
          :placeholder="__('Category')"
        />
        <p v-else class="text-sm text-ink-gray-8">
          {{ draft.category || "-" }}
        </p>
      </div>

      <div>
        <label class="block text-xs text-ink-gray-5 mb-1">{{
          __("Mapped ticket type")
        }}</label>
        <Link
          v-if="editable"
          class="form-control-core w-full"
          doctype="HD Ticket Type"
          :modelValue="draft.mapped_ticket_type"
          :placeholder="__('Ticket Type')"
          @update:model-value="(v: string) => (draft.mapped_ticket_type = v || '')"
        />
        <p v-else class="text-sm text-ink-gray-8">
          {{ draft.mapped_ticket_type || "-" }}
        </p>
      </div>

      <div>
        <label class="block text-xs text-ink-gray-5 mb-1">{{
          __("Priority")
        }}</label>
        <Link
          v-if="editable"
          class="form-control-core w-full"
          doctype="HD Ticket Priority"
          :modelValue="draft.priority"
          :placeholder="__('Priority')"
          @update:model-value="(v: string) => (draft.priority = v || '')"
        />
        <p v-else class="text-sm text-ink-gray-8">{{ draft.priority || "-" }}</p>
      </div>

      <div>
        <label class="block text-xs text-ink-gray-5 mb-1">{{
          __("Summary")
        }}</label>
        <textarea
          v-if="editable"
          v-model="draft.summary"
          rows="3"
          class="w-full rounded border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:outline-none focus:ring-1 focus:ring-outline-gray-3"
          :placeholder="__('Summary')"
        />
        <p v-else class="text-sm text-ink-gray-8 whitespace-pre-wrap">
          {{ draft.summary || "-" }}
        </p>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block text-xs text-ink-gray-5 mb-1">{{
            __("Suggested role")
          }}</label>
          <TextInput
            v-if="editable"
            v-model="draft.suggested_role"
            :placeholder="__('Role')"
          />
          <p v-else class="text-sm text-ink-gray-8">
            {{ draft.suggested_role || "-" }}
          </p>
        </div>
        <div>
          <label class="block text-xs text-ink-gray-5 mb-1">{{
            __("Suggested team")
          }}</label>
          <Link
            v-if="editable"
            class="form-control-core w-full"
            doctype="HD Team"
            :modelValue="draft.suggested_team"
            :placeholder="__('Team')"
            @update:model-value="(v: string) => (draft.suggested_team = v || '')"
          />
          <p v-else class="text-sm text-ink-gray-8">
            {{ draft.suggested_team || "-" }}
          </p>
        </div>
      </div>

      <div>
        <label class="block text-xs text-ink-gray-5 mb-1">{{
          __("Suggested agent")
        }}</label>
        <Link
          v-if="editable"
          class="form-control-core w-full"
          doctype="HD Agent"
          :modelValue="draft.suggested_agent"
          :placeholder="__('Agent')"
          @update:model-value="(v: string) => (draft.suggested_agent = v || '')"
        />
        <p v-else class="text-sm text-ink-gray-8">
          {{ draft.suggested_agent || "-" }}
        </p>
      </div>

      <label class="flex items-center gap-2 text-sm text-ink-gray-7">
        <input
          type="checkbox"
          class="rounded border-outline-gray-3"
          :disabled="!editable"
          v-model="draft.auto_handleable"
        />
        {{ __("Auto-handleable") }}
      </label>

      <div v-if="originalResult && analysis?.is_edited">
        <p class="text-xs text-ink-gray-5">
          {{ __("Original AI suggestion") }}:
          {{ originalResult.summary || originalResult.category || "-" }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link } from "@/components";
import { __ } from "@/translation";
import type { AIAnalysis, AIDraft } from "@/types/ai";
import { TextInput } from "frappe-ui";

defineProps<{
  draft: AIDraft;
  editable: boolean;
  analysis?: AIAnalysis | null;
  originalResult?: Record<string, any> | null;
}>();
</script>
