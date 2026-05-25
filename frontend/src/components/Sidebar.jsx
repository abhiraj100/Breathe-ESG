import { LayoutDashboard, Upload, ClipboardList, FileWarning, History, LogOut, Leaf } from 'lucide-react';

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'ingest', label: 'Ingest Data', icon: Upload },
  { id: 'review', label: 'Review Records', icon: ClipboardList },
  { id: 'flagged', label: 'Flagged', icon: FileWarning },
  { id: 'batches', label: 'Batch History', icon: History },
];

export default function Sidebar({ active, setActive, user, onLogout }) {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-60 bg-slate-900 border-r border-slate-800 flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-forest-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <Leaf className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-display text-base font-bold text-white leading-tight">Breathe ESG</div>
              <div className="text-xs text-slate-500 leading-tight">{user?.tenant?.name || 'Platform'}</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActive(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active === id
                  ? 'bg-forest-600/20 text-forest-400 border border-forest-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 py-4 border-t border-slate-800">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-forest-800 flex items-center justify-center text-forest-300 text-sm font-bold flex-shrink-0">
              {(user?.full_name || user?.username || 'U')[0].toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-slate-200 truncate">{user?.full_name || user?.username}</div>
              <div className="text-xs text-slate-500 capitalize">{user?.role || 'analyst'}</div>
            </div>
          </div>
          <button onClick={onLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-red-400 hover:bg-red-900/10 rounded-lg transition-colors">
            <LogOut className="w-4 h-4" />Logout
          </button>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-800 z-50">
        <div className="flex justify-around py-2">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActive(id)}
              className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors ${
                active === id ? 'text-forest-400' : 'text-slate-500'
              }`}>
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{label.split(' ')[0]}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
