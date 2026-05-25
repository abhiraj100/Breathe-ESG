import { useState } from 'react';
import { auth } from '../api';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await auth.login(username, password);
      onLogin(res.data);
    } catch {
      setError('Invalid credentials. Try admin/admin123');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-forest-600 rounded-xl flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-6 h-6 text-white fill-current">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
              </svg>
            </div>
            <span className="font-display text-2xl font-bold text-white tracking-tight">Breathe ESG</span>
          </div>
          <p className="text-slate-400 text-sm">Emissions Intelligence Platform</p>
        </div>

        <div className="card">
          <h2 className="font-display text-xl font-bold mb-6 text-white">Sign in</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-1.5 block">Username</label>
              <input
                className="input"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                required
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-1.5 block">Password</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            {error && <p className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded-lg px-3 py-2">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-2.5 mt-2"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
          <div className="mt-5 pt-4 border-t border-slate-800">
            <p className="text-xs text-slate-500 text-center">Demo credentials</p>
            <div className="flex gap-2 mt-2">
              <button onClick={() => { setUsername('admin'); setPassword('admin123'); }}
                className="flex-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg py-1.5 transition-colors">
                admin / admin123
              </button>
              <button onClick={() => { setUsername('analyst'); setPassword('analyst123'); }}
                className="flex-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg py-1.5 transition-colors">
                analyst / analyst123
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
