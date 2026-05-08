export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  city?: string;
  state?: string;
  is_remote: boolean;
  job_url: string;
  date_posted?: string;
  salary?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  description?: string;
  relevance_score: number;
  tier?: string;
  search_archetype?: string;
  source_board?: string;
  found_on_boards?: string;
  matched_strong?: string;
  matched_moderate?: string;
  matched_negative?: string;
  salary_flag?: string;
  has_analysis: boolean;
  analysis_file?: string;
}

export interface JobsResponse {
  jobs: Job[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface DashboardStats {
  total_jobs: number;
  shortlisted: number;
  consider: number;
  discarded: number;
  with_analysis: number;
  avg_score: number;
  top_archetypes: Record<string, number>;
  top_companies: { name: string; count: number; avg_score: number }[];
  score_distribution: Record<string, number>;
  boards_breakdown: Record<string, number>;
  remote_count: number;
  last_scrape?: string;
}

export interface PipelineStatus {
  running: boolean;
  step?: string;
  progress?: string;
  started_at?: string;
  last_run?: string;
  last_run_stats?: Record<string, unknown>;
}

export interface ValidationResult {
  matched_keywords: string[];
  missing_keywords: string[];
  coverage_percent: number;
  total_keywords: number;
}

export interface ResumeResponse {
  success: boolean;
  tex_path?: string;
  pdf_path?: string;
  cover_letter_path?: string;
  analysis_path?: string;
  message: string;
  validation?: ValidationResult;
}
