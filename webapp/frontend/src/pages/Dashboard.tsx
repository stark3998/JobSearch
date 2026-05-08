import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { DashboardStats } from '../types';

function StatCard({ label, value, color = 'text-text-primary', sub }: { label: string; value: string | number; color?: string; sub?: string }) {
  return (
    <div className="bg-surface-card rounded-xl p-5 border border-border">
      <p className="text-xs uppercase tracking-wider text-text-secondary mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-text-secondary mt-1">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStats().then(setStats).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-text-secondary">Loading dashboard...</div>;
  if (!stats) return <div className="p-8 text-text-secondary">No data yet. Run the pipeline first.</div>;

  const archetypeEntries = Object.entries(stats.top_archetypes);
  const scoreDist = Object.entries(stats.score_distribution);
  const maxScoreCount = Math.max(...scoreDist.map(([, v]) => v), 1);

  return (
    <div className="p-6 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-text-secondary text-sm mt-1">
          {stats.last_scrape ? `Last scrape: ${stats.last_scrape}` : 'No scrape data yet'}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        <StatCard label="Total Jobs" value={stats.total_jobs} />
        <StatCard label="Shortlisted" value={stats.shortlisted} color="text-tier-shortlist" />
        <StatCard label="Consider" value={stats.consider} color="text-tier-consider" />
        <StatCard label="Discarded" value={stats.discarded} color="text-tier-discard" />
        <StatCard label="Analyzed" value={stats.with_analysis} color="text-primary-600" />
        <StatCard label="Avg Score" value={stats.avg_score} sub={`${stats.remote_count} remote`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-card rounded-xl p-5 border border-border">
          <h2 className="text-sm font-semibold mb-4 text-text-secondary uppercase tracking-wider">Score Distribution</h2>
          <div className="space-y-2">
            {scoreDist.map(([range, count]) => (
              <div key={range} className="flex items-center gap-3">
                <span className="text-xs text-text-secondary w-10">{range}</span>
                <div className="flex-1 bg-surface rounded-full h-5 overflow-hidden">
                  <div
                    className="h-full bg-primary-600 rounded-full transition-all"
                    style={{ width: `${(count / maxScoreCount) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-text-secondary w-8 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-surface-card rounded-xl p-5 border border-border">
          <h2 className="text-sm font-semibold mb-4 text-text-secondary uppercase tracking-wider">By Archetype</h2>
          <div className="space-y-3">
            {archetypeEntries.map(([name, count]) => (
              <div key={name} className="flex justify-between items-center">
                <span className="text-sm truncate mr-2">{name}</span>
                <span className="text-sm font-mono text-primary-600">{count}</span>
              </div>
            ))}
            {archetypeEntries.length === 0 && <p className="text-sm text-text-secondary">No data</p>}
          </div>
        </div>

        <div className="bg-surface-card rounded-xl p-5 border border-border">
          <h2 className="text-sm font-semibold mb-4 text-text-secondary uppercase tracking-wider">By Board</h2>
          <div className="space-y-3">
            {Object.entries(stats.boards_breakdown).map(([board, count]) => (
              <div key={board} className="flex justify-between items-center">
                <span className="text-sm capitalize">{board}</span>
                <span className="text-sm font-mono text-primary-600">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-surface-card rounded-xl p-5 border border-border">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Top Companies</h2>
          <Link to="/jobs" className="text-xs text-primary-600 hover:text-primary-500">
            View all jobs →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-secondary text-xs uppercase tracking-wider border-b border-border">
                <th className="text-left py-2 pr-4">Company</th>
                <th className="text-right py-2 px-4">Jobs</th>
                <th className="text-right py-2">Avg Score</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_companies.map((c) => (
                <tr key={c.name} className="border-b border-border/50 hover:bg-surface-hover/50">
                  <td className="py-2.5 pr-4 font-medium">{c.name}</td>
                  <td className="py-2.5 px-4 text-right font-mono">{c.count}</td>
                  <td className="py-2.5 text-right font-mono text-primary-600">{c.avg_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
