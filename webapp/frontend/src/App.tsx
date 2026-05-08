import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import JobDetail from './pages/JobDetail';
import Pipeline from './pages/Pipeline';
import Resumes from './pages/Resumes';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '⊞' },
  { to: '/jobs', label: 'Jobs', icon: '⊡' },
  { to: '/pipeline', label: 'Pipeline', icon: '⊳' },
  { to: '/resumes', label: 'Resumes', icon: '⊟' },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <nav className="w-56 bg-surface-card border-r border-border flex flex-col shrink-0">
          <div className="p-5 border-b border-border">
            <h1 className="text-lg font-bold text-primary-600 tracking-tight">JobSearch</h1>
            <p className="text-xs text-text-secondary mt-1">Pipeline Dashboard</p>
          </div>
          <div className="flex flex-col gap-1 p-3 flex-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                  }`
                }
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </div>
          <div className="p-4 border-t border-border text-xs text-text-secondary">
            Jatin Madan
          </div>
        </nav>
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/jobs/:id" element={<JobDetail />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/resumes" element={<Resumes />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
