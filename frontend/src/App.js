import { useState, useEffect } from 'react';
import { auth } from './api';
import Login from './pages/Login';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Ingest from './pages/Ingest';
import Review from './pages/Review';
import Batches from './pages/Batches';

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="w-6 h-6 border-2 border-slate-700 border-t-forest-400 rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [active, setActive] = useState('dashboard');

  useEffect(() => {
    auth.me()
      .then(r => setUser(r.data))
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);

  const handleLogout = async () => {
    await auth.logout().catch(() => {});
    setUser(null);
  };

  if (checking) return <PageLoader />;
  if (!user) return <Login onLogin={setUser} />;

  const pages = {
    dashboard: <Dashboard />,
    ingest: <Ingest onIngested={() => {}} />,
    review: <Review />,
    flagged: <Review flaggedOnly />,
    batches: <Batches />,
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <Sidebar active={active} setActive={setActive} user={user} onLogout={handleLogout} />
      <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
          {pages[active] || <Dashboard />}
        </div>
      </main>
    </div>
  );
}
