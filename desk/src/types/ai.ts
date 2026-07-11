export type AIAnalysisStatus =
  | "Pending"
  | "Completed"
  | "Failed"
  | "Confirmed"
  | "Rejected";

export type AISource = "Mock" | "LLM";

export interface AIEvidenceItem {
  claim?: string;
  quote?: string;
  source?: string;
  weight?: number;
  rule?: string;
}

export interface AIMissingInfoItem {
  field?: string;
  label?: string;
  reason?: string;
}

export interface AIAutoHandlePlan {
  title?: string;
  steps?: string[];
  simulated_result?: string | Record<string, any>;
  simulated?: boolean;
  warnings?: string[];
  mock_patch?: Record<string, any>;
}

export interface AIBranch {
  branch: "missing_info" | "low_confidence" | "auto_handle" | "manual" | string;
  label?: string;
  reason?: string;
  confidence_threshold?: number;
}

export interface AIAnalysis {
  name: string;
  ticket: string;
  status: AIAnalysisStatus;
  source: AISource;
  analyzer?: string;
  model_name?: string;
  category?: string;
  mapped_ticket_type?: string | null;
  priority?: string | null;
  summary?: string;
  confidence?: number;
  evidence?: AIEvidenceItem[] | string;
  suggested_role?: string | null;
  suggested_team?: string | null;
  suggested_agent?: string | null;
  auto_handleable?: number | boolean;
  auto_handle_plan?: AIAutoHandlePlan | string | null;
  missing_info?: AIMissingInfoItem[] | string[] | string;
  handoff_reason?: string | null;
  original_result?: Record<string, any> | string | null;
  is_edited?: number | boolean;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  rejection_reason?: string | null;
  error_message?: string | null;
  creation?: string;
  modified?: string;
  branch?: AIBranch;
}

export interface AIConfirmResult {
  analysis: AIAnalysis;
  applied_fields: string[];
  warnings: string[];
  ticket: Record<string, any>;
  idempotent?: boolean;
}

export type AIDraft = {
  category: string;
  mapped_ticket_type: string;
  priority: string;
  summary: string;
  confidence: number | null;
  suggested_role: string;
  suggested_team: string;
  suggested_agent: string;
  auto_handleable: boolean;
  handoff_reason: string;
};
