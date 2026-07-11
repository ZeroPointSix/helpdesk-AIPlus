<template>
  <Dialog
    :title="__('Merge with another category')"
    @after-leave="
      () => {
        toCategory = null;
      }
    "
    v-model:open="showDialog"
  >
    <template #default>
      <p class="text-p-base text-ink-gray-8 mb-4">
        {{
          __(
            "This will move all articles of the {0} category to the selected category. This change is irreversible!",
            categoryTitle
          )
        }}
      </p>
      <Link
        class="form-control"
        doctype="HD Article Category"
        :placeholder="__('Select Category')"
        v-model="toCategory"
        :label="__('Category')"
        :page-length="100"
      />
    </template>
    <template #actions>
      <Button
        class="w-full"
        variant="solid"
        :label="__('Merge')"
        @click="emit('merge', categoryId, toCategory)"
      />
    </template>
  </Dialog>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { Dialog } from "frappe-ui";
import { Link } from "@/components";
defineProps<{
  categoryId: string;
  categoryTitle: string;
}>();
const emit = defineEmits(["merge"]);
const showDialog = defineModel<boolean>();

const toCategory = ref("");
</script>
