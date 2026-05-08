import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Job, JobsResponse } from '../types';

const TIER_COLORS: Record<string, string> = {
  shortlist: 'bg-tier-shortlist/20 text-tier-shortlist border-tier-shortlist/30',
  consider: 'bg-tier-consider/20 text-tier-consider border-tier-consider/30',
  discard: 'bg-tier-discard/20 text-tier-discard border-tier-discard/30',
};

const ARCHETYPE_SHORT: Record<string, string> = {
  cloud_security: 'Cloud Sec',
  security_architecture: 'Sec Arch',
  software_security: 'SW Sec',
  cloud_devops: 'DevOps',
};

export default function Jobs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<JobsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get('search') || '');

  const page = parseInt(searchParams.get('page') || '1');
  const tier = searchParams.get('tier') || '';
  const archetype = searchParams.get('archetype') || '';
  const sortBy = searchParams.get('sort_by') || 'relevance_score';
  const sortOrder = searchParams.get('sort_order') || 'desc';

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getJobs({
        page,
        per_page: 25,
        tier: tier || undefined,
        archetype: archetype || undefined,
        search: search || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setData(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [page, tier, archetype, search, sortBy, sortOrder]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    if (key !== 'page') next.set('page', '1');
    setSearchParams(next);
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    updateParam('search', search);
  }

  function toggleSort(col: string) {
    if (sortBy === col) {
      updateParam('sort_order', sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      const next = new URLSearchParams(searchParams);
      next.set('sort_by', col);
      next.set('sort_order', 'desc');
      next.set('page', '1');
      setSearchParams(next);
    }
  }

  const sortIcon = (col: string) => {
    if (sortBy !== col) return '';
    return sortOrder === 'desc' ? ' ↓' : ' ↑';
  };

  return (
    <div className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <div className="flex gap-2 flex-wrap">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search jobs..."
              className="bg-surface-card border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-primary-500 w-52"
            />
            <button type="submit" className="bg-primary-600 hover:bg-primary-700 text-white text-sm px-3 py-1.5 rounded-lg">
              Search
            </button>
          </form>
          <select value={tier} onChange={(e) => updateParam('tier', e.target.value)} className="bg-surface-card border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary">
            <option value="">All tiers</option>
            <option value="shortlist">Shortlist</option>
            <option value="consider">Consider</option>
            <option value="discard">Discard</option>
          </select>
          <select value={archetype} onChange={(e) => updateParam('archetype', e.target.value)} className="bg-surface-card border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary">
            <option value="">All archetypes</option>
            <option value="cloud_security">Cloud Security</option>
            <option value="security_architecture">Security Architecture</option>
            <option value="software_security">Software Security</option>
            <option value="cloud_devops">Cloud DevOps</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-text-secondary py-12 text-center">Loading jobs...</div>
      ) : !data || data.jobs.length === 0 ? (
        <div className="text-text-secondary py-12 text-center">
          No jobs found. {!tier && !archetype && !search ? 'Run the pipeline first.' : 'Try different filters.'}
        </div>
      ) : (
        <>
          <div className="bg-surface-card rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-secondary text-xs uppercase tracking-wider border-b border-border bg-surface-card">
                  <th className="text-left py-3 px-4 cursor-pointer hover:text-text-primary" onClick={() => toggleSort('relevance_score')}>
                    Score{sortIcon('relevance_score')}
                  </th>
                  <th className="text-left py-3 px-4">Tier</th>
                  <th className="text-left py-3 px-4 cursor-pointer hover:text-text-primary" onClick={() => toggleSort('company')}>
                    Company{sortIcon('company')}
                  </th>
                  <th className="text-left py-3 px-4 cursor-pointer hover:text-text-primary" onClick={() => toggleSort('title')}>
                    Title{sortIcon('title')}
                  </th>
                  <th className="text-left py-3 px-4">Location</th>
                  <th className="text-left py-3 px-4">Archetype</th>
                  <th className="text-left py-3 px-4">Salary</th>
                  <th className="text-center py-3 px-4">Analysis</th>
                  <th className="text-center py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.jobs.map((job) => (
                  <JobRow key={job.id} job={job} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-4 text-sm text-text-secondary">
            <span>{data.total} jobs total</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => updateParam('page', String(page - 1))}
                className="px-3 py-1 bg-surface-card border border-border rounded disabled:opacity-30 hover:bg-surface-hover"
              >
                Prev
              </button>
              <span className="px-3 py-1">
                Page {data.page} of {data.total_pages}
              </span>
              <button
                disabled={page >= data.total_pages}
                onClick={() => updateParam('page', String(page + 1))}
                className="px-3 py-1 bg-surface-card border border-border rounded disabled:opacity-30 hover:bg-surface-hover"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function JobRow({ job }: { job: Job }) {
  const tierClass = TIER_COLORS[job.tier || ''] || 'bg-surface text-text-secondary border-border';

  return (
    <tr className="border-b border-border/50 hover:bg-surface-hover/50 transition-colors">
      <td className="py-3 px-4">
        <span className="font-mono font-bold text-primary-400">{job.relevance_score}</span>
      </td>
      <td className="py-3 px-4">
        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${tierClass}`}>
          {job.tier}
        </span>
      </td>
      <td className="py-3 px-4 font-medium max-w-[150px] truncate">{job.company}</td>
      <td className="py-3 px-4 max-w-[200px] truncate">
        <Link to={`/jobs/${job.id}`} className="text-primary-400 hover:text-primary-300 hover:underline">
          {job.title}
        </Link>
      </td>
      <td className="py-3 px-4 text-text-secondary text-xs">
        {job.location}
        {job.is_remote && <span className="ml-1 text-tier-shortlist">(Remote)</span>}
      </td>
      <td className="py-3 px-4">
        <span className="text-xs bg-primary-600/10 text-primary-300 px-2 py-0.5 rounded">
          {ARCHETYPE_SHORT[job.search_archetype || ''] || job.search_archetype || '—'}
        </span>
      </td>
      <td className="py-3 px-4 text-xs text-text-secondary">{job.salary || '—'}</td>
      <td className="py-3 px-4 text-center">
        {job.has_analysis ? (
          <span className="text-tier-shortlist text-xs">Yes</span>
        ) : (
          <span className="text-text-secondary text-xs">—</span>
        )}
      </td>
      <td className="py-3 px-4 text-center">
        {job.job_url && (
          <a href={job.job_url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary-400 hover:text-primary-300">
            Apply
          </a>
        )}
      </td>
    </tr>
  );
}
