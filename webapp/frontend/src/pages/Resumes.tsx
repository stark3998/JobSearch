import { useEffect, useState } from 'react';
import { api } from '../api';

interface Resume {
  name: string;
  tex: string;
  has_pdf: boolean;
  has_cover_letter: boolean;
  cover_letter?: string;
  modified: number;
  archived: boolean;
  archive_path?: string;
}

export default function Resumes() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewName, setPreviewName] = useState<string | null>(null);

  useEffect(() => {
    api.listResumes().then(setResumes).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-text-secondary">Loading resumes...</div>;

  const current = resumes.filter((r) => !r.archived);
  const archived = resumes.filter((r) => r.archived);

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-2xl font-bold mb-6">Generated Resumes</h1>

      {current.length === 0 && archived.length === 0 ? (
        <div className="bg-surface-card rounded-xl border border-border p-12 text-center">
          <p className="text-text-secondary mb-2">No resumes generated yet.</p>
          <p className="text-sm text-text-secondary">Go to Jobs, pick one, and click "Generate Resume & Cover Letter".</p>
        </div>
      ) : (
        <>
          {current.length > 0 && (
            <div className="space-y-3 mb-8">
              {current.map((r) => (
                <ResumeCard
                  key={r.tex}
                  resume={r}
                  expanded={previewName === r.tex}
                  onTogglePreview={() => setPreviewName(previewName === r.tex ? null : r.tex)}
                />
              ))}
            </div>
          )}

          {archived.length > 0 && (
            <>
              <h2 className="text-lg font-semibold text-text-secondary mb-3 mt-6">Archived</h2>
              <div className="space-y-2">
                {archived.map((r) => (
                  <ResumeCard
                    key={`${r.archive_path}/${r.tex}`}
                    resume={r}
                    expanded={previewName === `${r.archive_path}/${r.tex}`}
                    onTogglePreview={() => {
                      const key = `${r.archive_path}/${r.tex}`;
                      setPreviewName(previewName === key ? null : key);
                    }}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function ResumeCard({
  resume: r,
  expanded,
  onTogglePreview,
}: {
  resume: Resume;
  expanded: boolean;
  onTogglePreview: () => void;
}) {
  return (
    <div className={`bg-surface-card rounded-xl border border-border p-5 ${r.archived ? 'opacity-70' : ''}`}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium capitalize">
            {r.name.replace(/-/g, ' ')}
            {r.archived && (
              <span className="ml-2 text-xs text-text-secondary bg-surface px-2 py-0.5 rounded-full border border-border">
                archived
              </span>
            )}
          </h3>
          <p className="text-xs text-text-secondary mt-1">
            {r.tex} | Modified: {new Date(r.modified * 1000).toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2">
          {r.has_pdf && (
            <button
              type="button"
              onClick={onTogglePreview}
              className="text-sm px-3 py-1.5 bg-surface border border-border rounded-lg text-text-secondary hover:text-text-primary hover:border-primary-500/30 transition-colors"
            >
              {expanded ? 'Hide Preview' : 'Preview'}
            </button>
          )}
          <a
            href={`/api/resume/download/${r.tex}`}
            className="text-sm px-3 py-1.5 bg-surface border border-border rounded-lg text-text-secondary hover:text-text-primary hover:border-primary-500/30 transition-colors"
          >
            .tex
          </a>
          {r.has_pdf && (
            <a
              href={`/api/resume/download/${r.tex.replace('.tex', '.pdf')}`}
              className="text-sm px-3 py-1.5 bg-primary-600/20 border border-primary-600/30 rounded-lg text-primary-400 hover:bg-primary-600/30 transition-colors"
            >
              .pdf
            </a>
          )}
          {r.has_cover_letter && r.cover_letter && (
            <a
              href={`/api/resume/download/${r.cover_letter}`}
              className="text-sm px-3 py-1.5 bg-tier-consider/20 border border-tier-consider/30 rounded-lg text-tier-consider hover:bg-tier-consider/30 transition-colors"
            >
              Cover Letter
            </a>
          )}
        </div>
      </div>

      {expanded && r.has_pdf && (
        <div className="mt-4">
          <iframe
            src={`/api/resume/preview/${r.tex.replace('.tex', '.pdf')}`}
            title={`${r.name} PDF Preview`}
            className="w-full h-[700px] rounded-lg border border-border bg-white"
          />
        </div>
      )}
    </div>
  );
}
