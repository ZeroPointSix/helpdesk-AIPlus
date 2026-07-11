import { __ } from "@/translation";
import type {
  AIAnalysis,
  AIConfirmResult,
  AIDraft,
} from "@/types/ai";
import { reloadTicket } from "@/composables/useTicket";
import { createResource, toast } from "frappe-ui";
import {
  computed,
  isRef,
  reactive,
  ref,
  unref,
  watch,
  type MaybeRef,
} from "vue";

function emptyDraft(): AIDraft {
  return {
    category: "",
    mapped_ticket_type: "",
    priority: "",
    summary: "",
    confidence: null,
    suggested_role: "",
    suggested_team: "",
    suggested_agent: "",
    auto_handleable: false,
    handoff_reason: "",
  };
}

function analysisToDraft(analysis: AIAnalysis | null | undefined): AIDraft {
  if (!analysis) return emptyDraft();
  return {
    category: analysis.category || "",
    mapped_ticket_type: analysis.mapped_ticket_type || "",
    priority: analysis.priority || "",
    summary: analysis.summary || "",
    confidence:
      analysis.confidence === undefined || analysis.confidence === null
        ? null
        : Number(analysis.confidence),
    suggested_role: analysis.suggested_role || "",
    suggested_team: analysis.suggested_team || "",
    suggested_agent: analysis.suggested_agent || "",
    auto_handleable: Boolean(analysis.auto_handleable),
    handoff_reason: analysis.handoff_reason || "",
  };
}

function parseMaybeJson<T>(value: unknown, fallback: T): T {
  if (value == null || value === "") return fallback;
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as T;
    } catch {
      return fallback;
    }
  }
  return value as T;
}

export function useTicketAI(ticketId: MaybeRef<string>) {
  const ticketIdRef = isRef(ticketId) ? ticketId : ref(ticketId);
  const currentTicketId = () => String(unref(ticketIdRef) || "");

  const draft = reactive<AIDraft>(emptyDraft());
  const editing = ref(false);
  const showConfirmPreview = ref(false);
  const applyFields = ref<string[]>([
    "mapped_ticket_type",
    "priority",
    "summary",
    "suggested_team",
  ]);
  const simulation = ref<Record<string, any> | null>(null);
  const rejectReason = ref("");

  const analysisResource = createResource({
    url: "helpdesk.api.ai.get_latest_analysis",
    params: { ticket: currentTicketId() },
    auto: true,
    onSuccess(data: AIAnalysis | null) {
      if (data && !editing.value) {
        Object.assign(draft, analysisToDraft(data));
      }
      if (!data && !editing.value) {
        Object.assign(draft, emptyDraft());
      }
    },
  });

  const analyzeResource = createResource({
    url: "helpdesk.api.ai.analyze_ticket",
    // Omit source so server uses HD AI Settings / site_config (default Mock).
    makeParams: () => ({ ticket: currentTicketId() }),
    onSuccess(data: AIAnalysis) {
      analysisResource.data = data;
      Object.assign(draft, analysisToDraft(data));
      editing.value = false;
      simulation.value = null;
      if (data?.status === "Failed") {
        toast.error(data.error_message || __("AI analysis failed"));
      } else {
        toast.success(__("AI analysis completed"));
      }
    },
    onError(error: any) {
      const msg =
        error?.messages?.[0] || error?.message || __("AI analysis failed");
      toast.error(msg);
      // Best-effort refresh in case a Failed row was still written.
      analysisResource.reload();
    },
  });

  const updateResource = createResource({
    url: "helpdesk.api.ai.update_analysis",
    makeParams: () => ({
      name: analysis.value?.name,
      fields: draftPayload(),
    }),
    onSuccess(data: AIAnalysis) {
      analysisResource.data = data;
      Object.assign(draft, analysisToDraft(data));
      editing.value = false;
      toast.success(__("AI analysis updated"));
    },
    onError(error: any) {
      toast.error(error?.messages?.[0] || error?.message || __("Update failed"));
    },
  });

  const confirmResource = createResource({
    url: "helpdesk.api.ai.confirm_analysis",
    makeParams: () => ({
      name: analysis.value?.name,
      apply_fields: applyFields.value,
      fields: draftPayload(),
    }),
    onSuccess(data: AIConfirmResult) {
      analysisResource.data = data.analysis;
      Object.assign(draft, analysisToDraft(data.analysis));
      editing.value = false;
      showConfirmPreview.value = false;
      reloadTicket(currentTicketId());
      const warnings = data.warnings || [];
      if (warnings.length) {
        toast.success(
          `${__("AI analysis confirmed")}: ${warnings.join("; ")}`
        );
      } else {
        toast.success(__("AI analysis confirmed"));
      }
    },
    onError(error: any) {
      toast.error(
        error?.messages?.[0] || error?.message || __("Confirm failed")
      );
    },
  });

  const rejectResource = createResource({
    url: "helpdesk.api.ai.reject_analysis",
    makeParams: () => ({
      name: analysis.value?.name,
      reason: rejectReason.value || "",
    }),
    onSuccess(data: { analysis: AIAnalysis }) {
      analysisResource.data = data.analysis;
      editing.value = false;
      rejectReason.value = "";
      toast.success(__("AI analysis rejected"));
    },
    onError(error: any) {
      toast.error(
        error?.messages?.[0] || error?.message || __("Reject failed")
      );
    },
  });

  const simulateResource = createResource({
    url: "helpdesk.api.ai.simulate_auto_handle",
    makeParams: () => ({ name: analysis.value?.name }),
    onSuccess(data: Record<string, any>) {
      simulation.value = data;
      toast.success(__("Simulation completed (no real side effects)"));
    },
    onError(error: any) {
      toast.error(
        error?.messages?.[0] || error?.message || __("Simulation failed")
      );
    },
  });

  const analysis = computed<AIAnalysis | null>(
    () => (analysisResource.data as AIAnalysis) || null
  );

  const loading = computed(
    () =>
      Boolean(analysisResource.loading) ||
      Boolean(analyzeResource.loading) ||
      Boolean(updateResource.loading) ||
      Boolean(confirmResource.loading) ||
      Boolean(rejectResource.loading) ||
      Boolean(simulateResource.loading)
  );

  const simulating = computed(() => Boolean(simulateResource.loading));

  const uiPhase = computed(() => {
    if (analyzeResource.loading) return "loading";
    if (analysisResource.loading && !analysis.value) return "loading";
    if (analysisResource.error && !analysis.value) return "error";
    if (!analysis.value) return "empty";
    if (analysis.value.status === "Failed") return "failed";
    if (analysis.value.status === "Pending") return "loading";
    if (analysis.value.status === "Confirmed") return "confirmed";
    if (analysis.value.status === "Rejected") return "rejected";
    return "result";
  });

  const isEditable = computed(
    () => analysis.value?.status === "Completed" && editing.value
  );

  const canEdit = computed(() => analysis.value?.status === "Completed");
  const canConfirmOrReject = computed(
    () => analysis.value?.status === "Completed"
  );

  const evidence = computed(() =>
    parseMaybeJson(analysis.value?.evidence, [] as any[])
  );
  const missingInfo = computed(() =>
    parseMaybeJson(analysis.value?.missing_info, [] as any[])
  );
  const autoHandlePlan = computed(() =>
    parseMaybeJson(analysis.value?.auto_handle_plan, null as any)
  );
  const originalResult = computed(() =>
    parseMaybeJson(analysis.value?.original_result, null as any)
  );

  const isDirty = computed(() => {
    if (!analysis.value || analysis.value.status !== "Completed") return false;
    const base = analysisToDraft(analysis.value);
    return JSON.stringify(base) !== JSON.stringify({ ...draft });
  });

  function draftPayload() {
    return {
      category: draft.category,
      mapped_ticket_type: draft.mapped_ticket_type || null,
      priority: draft.priority || null,
      summary: draft.summary,
      confidence: draft.confidence,
      suggested_role: draft.suggested_role,
      suggested_team: draft.suggested_team || null,
      suggested_agent: draft.suggested_agent || null,
      auto_handleable: draft.auto_handleable ? 1 : 0,
      handoff_reason: draft.handoff_reason,
    };
  }

  function runAnalyze() {
    if (!currentTicketId()) return;
    analyzeResource.submit();
  }

  function startEdit() {
    Object.assign(draft, analysisToDraft(analysis.value));
    editing.value = true;
  }

  function cancelEdit() {
    Object.assign(draft, analysisToDraft(analysis.value));
    editing.value = false;
  }

  function saveDraft() {
    if (!analysis.value?.name) return;
    updateResource.submit();
  }

  function openConfirmPreview() {
    showConfirmPreview.value = true;
  }

  function confirmAdoption() {
    if (!analysis.value?.name) return;
    confirmResource.submit();
  }

  function rejectAnalysis() {
    if (!analysis.value?.name) return;
    rejectResource.submit();
  }

  function runSimulation() {
    if (!analysis.value?.name) return;
    simulateResource.submit();
  }

  function reload() {
    analysisResource.reload();
  }

  watch(
    ticketIdRef,
    (id) => {
      const ticket = String(id || "");
      analysisResource.update({ params: { ticket } });
      analysisResource.data = null;
      Object.assign(draft, emptyDraft());
      editing.value = false;
      simulation.value = null;
      showConfirmPreview.value = false;
      rejectReason.value = "";
      if (ticket) {
        analysisResource.reload();
      }
    }
  );

  return {
    analysis,
    analysisResource,
    draft,
    editing,
    loading,
    simulating,
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
    reload,
  };
}
