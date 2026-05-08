const BASE = '/api';

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  getStats: () => fetchJSON<import('./types').DashboardStats>('/jobs/stats'),

  getJobs: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== '') qs.set(k, String(v));
    }
    return fetchJSON<import('./types').JobsResponse>(`/jobs?${qs}`);
  },

  getJob: (id: number) => fetchJSON<{ job: import('./types').Job; analysis: string | null }>(`/jobs/${id}`),

  getPipelineStatus: () => fetchJSON<import('./types').PipelineStatus>('/pipeline/status'),

  runPipeline: (body: Record<string, unknown>) =>
    fetchJSON<{ status: string; message: string }>('/pipeline/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getArchetypes: () => fetchJSON<Record<string, { display_name: string; key: string }>>('/pipeline/archetypes'),
  getBoards: () => fetchJSON<string[]>('/pipeline/boards'),

  generateResume: (jobId: number, archetypeOverride?: string, onePage?: boolean) =>
    fetchJSON<import('./types').ResumeResponse>('/resume/generate', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, archetype_override: archetypeOverride, one_page: onePage ?? false }),
    }),

  listResumes: () => fetchJSON<{
    name: string;
    tex: string;
    has_pdf: boolean;
    has_cover_letter: boolean;
    cover_letter?: string;
    modified: number;
    archived: boolean;
    archive_path?: string;
  }[]>('/resume/list'),

  getAnalysis: (filename: string) => fetchJSON<{ content: string }>(`/resume/analysis/${filename}`),
};
