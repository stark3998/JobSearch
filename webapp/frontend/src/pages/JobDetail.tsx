import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import type { Job, ResumeResponse } from '../types';

const ARCHETYPE_OPTIONS = [
  { key: 'cloud_security', label: 'Cloud Security' },
  { key: 'security_architecture', label: 'Security Architecture' },
  { key: 'software_security', label: 'Software Security' },
  { key: 'cloud_devops', label: 'Cloud DevOps' },
];

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [resumeResult, setResumeResult] = useState<ResumeResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [archetypeOverride, setArchetypeOverride] = useState<string>('');
  const [onePage, setOnePage] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.getJob(parseInt(id))
      .then((res) => {
        setJob(res.job);
        setAnalysis(res.analysis);
        setArchetypeOverride(res.job.search_archetype || '');
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  async function handleGenerate() {
    if (!job) return;
    setGenerating(true);
    setResumeResult(null);
    try {
      const res = await api.generateResume(job.id, archetypeOverride || undefined, onePage);
      setResumeResult(res);
    } catch (e) {
      setResumeResult({ success: false, message: String(e) });
    }
    setGenerating(false);
  }

  if (loading) return <div className="p-8 text-text-secondary">Loading...</div>;
  if (!job) return <div className="p-8 text-text-secondary">Job not found.</div>;

  const tierColor = job.tier === 'shortlist' ? 'text-tier-shortlist' : job.tier === 'consider' ? 'text-tier-consider' : 'text-text-secondary';

  return (
    <div className="p-6 max-w-5xl">
      <Link to="/jobs" className="text-sm text-primary-600 hover:text-primary-500 mb-4 inline-block">
        ← Back to Jobs
      </Link>

      {/* Job header card */}
      <div className="bg-surface-card rounded-xl border border-border p-6 mb-6">
        <div className="flex flex-wrap justify-between items-start gap-4">
          <div>
            <h1 className="text-2xl font-bold mb-1">{job.title}</h1>
            <p className="text-lg text-text-secondary">{job.company}</p>
            <div className="flex flex-wrap gap-3 mt-3 text-sm">
              <span className="text-text-secondary">{job.location}</span>
              {job.is_remote && <span className="text-tier-shortlist">Remote</span>}
              {job.salary && <span className="text-text-secondary">{job.salary}</span>}
              {job.date_posted && <span className="text-text-secondary">Posted: {job.date_posted}</span>}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="text-right">
              <span className="text-4xl font-bold font-mono text-primary-600">{job.relevance_score}</span>
              <p className={`text-sm font-medium uppercase ${tierColor}`}>{job.tier}</p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {job.search_archetype && (
            <span className="text-xs bg-primary-50 text-primary-700 px-2.5 py-1 rounded-full border border-primary-100">
              {job.search_archetype.replace(/_/g, ' ')}
            </span>
          )}
          {job.source_board && (
            <span className="text-xs bg-surface text-text-secondary px-2.5 py-1 rounded-full border border-border">
              {job.source_board}
            </span>
          )}
          {job.found_on_boards && (
            <span className="text-xs bg-surface text-text-secondary px-2.5 py-1 rounded-full border border-border">
              Found on: {job.found_on_boards}
            </span>
          )}
        </div>

        {(job.matched_strong || job.matched_moderate) && (
          <div className="mt-4 pt-4 border-t border-border">
            {job.matched_strong && (
              <div className="mb-2">
                <span className="text-xs text-text-secondary uppercase tracking-wider">Strong matches: </span>
                <span className="text-sm text-tier-shortlist">{job.matched_strong}</span>
              </div>
            )}
            {job.matched_moderate && (
              <div className="mb-2">
                <span className="text-xs text-text-secondary uppercase tracking-wider">Moderate matches: </span>
                <span className="text-sm text-tier-consider">{job.matched_moderate}</span>
              </div>
            )}
            {job.matched_negative && (
              <div>
                <span className="text-xs text-text-secondary uppercase tracking-wider">Negative flags: </span>
                <span className="text-sm text-red-600">{job.matched_negative}</span>
              </div>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-5 pt-4 border-t border-border">
          <div className="flex flex-wrap items-end gap-3">
            {job.job_url && (
              <a href={job.job_url} target="_blank" rel="noopener noreferrer"
                className="bg-primary-600 hover:bg-primary-700 text-white text-sm px-4 py-2.5 rounded-lg font-medium transition-colors">
                Apply Now
              </a>
            )}
            <div className="flex items-end gap-2">
              <div>
                <label className="block text-xs text-text-secondary mb-1">Archetype</label>
                <select
                  value={archetypeOverride}
                  onChange={(e) => setArchetypeOverride(e.target.value)}
                  aria-label="Resume archetype"
                  title="Resume archetype"
                  className="bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text-primary"
                >
                  {ARCHETYPE_OPTIONS.map((a) => (
                    <option key={a.key} value={a.key}>{a.label}</option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none pb-1">
                <input
                  type="checkbox"
                  checked={onePage}
                  onChange={(e) => setOnePage(e.target.checked)}
                  className="rounded border-border accent-primary-500"
                />
                1-Page
              </label>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={generating}
                className="bg-tier-shortlist/20 hover:bg-tier-shortlist/30 text-tier-shortlist border border-tier-shortlist/30 text-sm px-5 py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50 whitespace-nowrap"
              >
                {generating ? (
                  <span className="flex items-center gap-2">
                    <span className="w-3 h-3 border-2 border-tier-shortlist/30 border-t-tier-shortlist rounded-full animate-spin" />
                    Generating...
                  </span>
                ) : (
                  'Generate Resume & Cover Letter'
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Generation result */}
        {resumeResult && (
          <div className={`mt-4 rounded-xl border p-5 ${resumeResult.success ? 'bg-tier-shortlist/5 border-tier-shortlist/20' : 'bg-red-50 border-red-200'}`}>
            <div className="flex items-start gap-3">
              <span className={`text-lg mt-0.5 ${resumeResult.success ? 'text-tier-shortlist' : 'text-red-600'}`}>
                {resumeResult.success ? '✓' : '✗'}
              </span>
              <div className="flex-1">
                <p className={`font-medium text-sm ${resumeResult.success ? 'text-tier-shortlist' : 'text-red-600'}`}>
                  {resumeResult.success ? 'Resume & Cover Letter Generated' : 'Generation Failed'}
                </p>
                <p className="text-sm text-text-secondary mt-1">{resumeResult.message}</p>

                {resumeResult.success && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {resumeResult.tex_path && (
                      <a href={`/api/resume/download/${resumeResult.tex_path.split('/').pop()}`}
                        className="inline-flex items-center gap-1.5 text-xs bg-surface border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:text-text-primary hover:border-primary-300 transition-colors">
                        <span>📄</span> Resume (.tex)
                      </a>
                    )}
                    {resumeResult.pdf_path && (
                      <a href={`/api/resume/download/${resumeResult.pdf_path.split('/').pop()}`}
                        className="inline-flex items-center gap-1.5 text-xs bg-primary-50 border border-primary-200 rounded-lg px-3 py-1.5 text-primary-600 hover:bg-primary-100 transition-colors">
                        <span>📑</span> Resume (.pdf)
                      </a>
                    )}
                    {resumeResult.cover_letter_path && (
                      <a href={`/api/resume/download/${resumeResult.cover_letter_path.split('/').pop()}`}
                        className="inline-flex items-center gap-1.5 text-xs bg-tier-consider/20 border border-tier-consider/30 rounded-lg px-3 py-1.5 text-tier-consider hover:bg-tier-consider/30 transition-colors">
                        <span>✉</span> Cover Letter (.md)
                      </a>
                    )}
                    {resumeResult.analysis_path && (
                      <a href={`/api/resume/download/${resumeResult.analysis_path.split('/').pop()}`}
                        className="inline-flex items-center gap-1.5 text-xs bg-surface border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:text-text-primary hover:border-primary-300 transition-colors">
                        <span>📊</span> JD Analysis (.md)
                      </a>
                    )}
                  </div>
                )}

                {/* PDF Preview */}
                {resumeResult.pdf_path && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium text-text-secondary mb-2">PDF Preview</h4>
                    <iframe
                      src={`/api/resume/preview/${resumeResult.pdf_path.split('/').pop()}`}
                      title="Resume PDF Preview"
                      className="w-full h-[600px] rounded-lg border border-border bg-white"
                    />
                  </div>
                )}

                {/* JD Keyword Validation */}
                {resumeResult.validation && (
                  <div className="mt-4 pt-4 border-t border-border/50">
                    <div className="flex items-center gap-3 mb-3">
                      <h4 className="text-sm font-medium text-text-secondary">JD Keyword Validation</h4>
                      <span className={`text-lg font-bold font-mono ${
                        resumeResult.validation.coverage_percent >= 80 ? 'text-tier-shortlist' :
                        resumeResult.validation.coverage_percent >= 60 ? 'text-tier-consider' : 'text-red-600'
                      }`}>
                        {resumeResult.validation.coverage_percent}%
                      </span>
                      <span className="text-xs text-text-secondary">
                        ({resumeResult.validation.matched_keywords.length}/{resumeResult.validation.total_keywords} keywords)
                      </span>
                    </div>

                    {resumeResult.validation.matched_keywords.length > 0 && (
                      <div className="mb-2">
                        <span className="text-xs text-tier-shortlist uppercase tracking-wider">Matched: </span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {resumeResult.validation.matched_keywords.map((kw) => (
                            <span key={kw} className="text-xs bg-tier-shortlist/10 text-tier-shortlist px-2 py-0.5 rounded-full border border-tier-shortlist/20">
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {resumeResult.validation.missing_keywords.length > 0 && (
                      <div>
                        <span className="text-xs text-red-600 uppercase tracking-wider">Missing: </span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {resumeResult.validation.missing_keywords.map((kw) => (
                            <span key={kw} className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full border border-red-200">
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Analysis / Description */}
      {analysis ? (
        <div className="bg-surface-card rounded-xl border border-border p-6 overflow-hidden">
          <h2 className="text-lg font-semibold mb-4">JD Analysis</h2>
          <div className="prose prose-sm max-w-none [&_h1]:text-xl [&_h1]:text-text-primary [&_h2]:text-base [&_h2]:text-primary-600 [&_h2]:mt-6 [&_h2]:mb-2 [&_table]:text-sm [&_th]:text-text-secondary [&_th]:text-left [&_th]:py-1 [&_th]:pr-4 [&_td]:py-1 [&_td]:pr-4 [&_hr]:border-border [&_strong]:text-text-primary [&_a]:text-primary-600 [&_code]:bg-surface [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-primary-700 [&_pre]:overflow-x-auto [&_pre]:bg-surface [&_pre]:p-3 [&_pre]:rounded-lg [&_code]:break-words [&_ul]:space-y-1 [&_ol]:space-y-1 [&_li]:text-text-secondary [&_p]:text-text-secondary [&_p]:break-words">
            <ReactMarkdown>{analysis}</ReactMarkdown>
          </div>
        </div>
      ) : (
        <div className="bg-surface-card rounded-xl border border-border p-6">
          <h2 className="text-lg font-semibold mb-4">Job Description</h2>
          {job.description ? (
            <div className="text-sm text-text-secondary whitespace-pre-wrap leading-relaxed">
              {job.description}
            </div>
          ) : (
            <p className="text-sm text-text-secondary">No description available.</p>
          )}
        </div>
      )}
    </div>
  );
}
