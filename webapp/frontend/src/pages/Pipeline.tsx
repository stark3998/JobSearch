import { useEffect, useState, useRef } from 'react';
import { api } from '../api';
import type { PipelineStatus } from '../types';

const BOARDS = ['indeed', 'linkedin', 'google', 'zip_recruiter', 'glassdoor'];
const ARCHETYPES = [
  { key: 'cloud_security', label: 'Cloud Security' },
  { key: 'security_architecture', label: 'Security Architecture' },
  { key: 'software_security', label: 'Software Security' },
  { key: 'cloud_devops', label: 'Cloud DevOps' },
];

export default function Pipeline() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [selectedBoards, setSelectedBoards] = useState<string[]>(['indeed']);
  const [selectedArchetypes, setSelectedArchetypes] = useState<string[]>(['cloud_security', 'cloud_devops']);
  const [hoursOld, setHoursOld] = useState(72);
  const [limit, setLimit] = useState(30);
  const [message, setMessage] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    api.getPipelineStatus().then(setStatus).catch(console.error);
  }, []);

  useEffect(() => {
    if (status?.running) {
      pollRef.current = setInterval(() => {
        api.getPipelineStatus().then(setStatus).catch(console.error);
      }, 3000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [status?.running]);

  async function handleRun() {
    setMessage('');
    try {
      const res = await api.runPipeline({
        boards: selectedBoards.length > 0 ? selectedBoards : undefined,
        archetypes: selectedArchetypes.length > 0 ? selectedArchetypes : undefined,
        hours_old: hoursOld,
        limit,
      });
      setMessage(res.message);
      api.getPipelineStatus().then(setStatus);
    } catch (e) {
      setMessage(String(e));
    }
  }

  function toggleBoard(b: string) {
    setSelectedBoards((prev) => prev.includes(b) ? prev.filter((x) => x !== b) : [...prev, b]);
  }

  function toggleArchetype(a: string) {
    setSelectedArchetypes((prev) => prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]);
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">Pipeline Control</h1>

      {status?.running && (
        <div className="bg-primary-600/10 border border-primary-600/30 rounded-xl p-5 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-primary-400 rounded-full animate-pulse" />
            <div>
              <p className="font-medium text-primary-400">Pipeline Running</p>
              <p className="text-sm text-text-secondary">
                Step: {status.step || '...'} — {status.progress || 'Working...'}
              </p>
              {status.started_at && (
                <p className="text-xs text-text-secondary mt-1">
                  Started: {new Date(status.started_at).toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {status?.last_run_stats && !status.running && (
        <div className="bg-tier-shortlist/10 border border-tier-shortlist/20 rounded-xl p-5 mb-6">
          <p className="font-medium text-tier-shortlist mb-2">Last Run Complete</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {Object.entries(status.last_run_stats).map(([k, v]) => (
              <div key={k}>
                <span className="text-text-secondary capitalize">{k}: </span>
                <span className="font-mono text-text-primary">{String(v)}</span>
              </div>
            ))}
          </div>
          {status.last_run && (
            <p className="text-xs text-text-secondary mt-2">
              Completed: {new Date(status.last_run).toLocaleString()}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-surface-card rounded-xl border border-border p-5">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Job Boards</h2>
          <div className="flex flex-wrap gap-2">
            {BOARDS.map((b) => (
              <button
                key={b}
                onClick={() => toggleBoard(b)}
                className={`text-sm px-3 py-1.5 rounded-lg border transition-colors capitalize ${
                  selectedBoards.includes(b)
                    ? 'bg-primary-600/20 text-primary-400 border-primary-600/30'
                    : 'bg-surface text-text-secondary border-border hover:border-primary-600/30'
                }`}
              >
                {b.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-surface-card rounded-xl border border-border p-5">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Role Archetypes</h2>
          <div className="flex flex-wrap gap-2">
            {ARCHETYPES.map((a) => (
              <button
                key={a.key}
                onClick={() => toggleArchetype(a.key)}
                className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${
                  selectedArchetypes.includes(a.key)
                    ? 'bg-primary-600/20 text-primary-400 border-primary-600/30'
                    : 'bg-surface text-text-secondary border-border hover:border-primary-600/30'
                }`}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-surface-card rounded-xl border border-border p-5">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">Settings</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm text-text-secondary">Hours old</label>
              <input
                type="number" value={hoursOld} onChange={(e) => setHoursOld(parseInt(e.target.value) || 72)}
                className="w-20 bg-surface border border-border rounded px-2 py-1 text-sm text-text-primary text-right"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-text-secondary">Max analyses</label>
              <input
                type="number" value={limit} onChange={(e) => setLimit(parseInt(e.target.value) || 30)}
                className="w-20 bg-surface border border-border rounded px-2 py-1 text-sm text-text-primary text-right"
              />
            </div>
          </div>
        </div>

        <div className="bg-surface-card rounded-xl border border-border p-5 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-2">Run Pipeline</h2>
            <p className="text-xs text-text-secondary mb-4">
              {selectedBoards.length} board(s), {selectedArchetypes.length} archetype(s), last {hoursOld}h
            </p>
          </div>
          <button
            onClick={handleRun}
            disabled={status?.running || selectedBoards.length === 0 || selectedArchetypes.length === 0}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-primary-600/30 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors"
          >
            {status?.running ? 'Running...' : 'Start Pipeline'}
          </button>
          {message && <p className="text-xs text-text-secondary mt-2">{message}</p>}
        </div>
      </div>
    </div>
  );
}
