import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { dashboard } from '../api';
import { TrendingUp, Clock, AlertTriangle, CheckCircle, XCircle, Leaf } from 'lucide-react';

const SCOPE_COLORS = { scope1: '#22c55e', scope2: '#3b82f6', scope3: '#f59e0b' };
const SCOPE_LABELS = { scope1: 'Scope 1', scope2: 'Scope 2', scope3: 'Scope 3' };

function StatCard({ icon: Icon, label, value, sub, color = 'forest' }) {
  const colorMap = {
    forest: 'text-forest-400 bg-forest-600/10 border-forest-600/20',
    amber: 'text-amber-400 bg-amber-600/10 border-amber-600/20',
    blue: 'text-blue-400 bg-blue-600/10 border-blue-600/20',
    red: 'text-red-400 bg-red-600/10 border-red-600/20',
  };
  return (
    <div className="card flex items-start gap-4">
      <div className={`p-2.5 rounded-lg border ${colorMap[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-slate-400 uppercase tracking-wider mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-white font-display">{value}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs">
      <p className="text-slate-300 mb-1">{label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.fill }}>{p.name}: {Number(p.value).toLocaleString(undefined, {maximumFractionDigits: 0})} kgCO₂e</p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboard.stats().then(r => { setStats(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-slate-400 text-sm">Loading dashboard...</div>
    </div>
  );
  if (!stats) return <div className="text-red-400 p-6">Failed to load dashboard data.</div>;

  const totalCO2e = stats.total_co2e_kg;
  const scopeData = Object.entries(stats.scope_breakdown).map(([k, v]) => ({
    name: SCOPE_LABELS[k], value: v, color: SCOPE_COLORS[k]
  })).filter(d => d.value > 0);

  const categoryData = stats.category_breakdown
    .sort((a, b) => b.co2e_kg - a.co2e_kg)
    .slice(0, 8)
    .map(c => ({ name: c.label.replace('Business Travel - ', 'Travel: ').replace('Purchased ', ''), value: c.co2e_kg }));

  const batchTypeColors = { sap: '#22c55e', utility: '#3b82f6', travel: '#f59e0b' };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Emissions overview — Q1 2024</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Leaf} label="Total CO₂e (approved)" color="forest"
          value={`${(totalCO2e / 1000).toFixed(1)}t`} sub="metric tonnes CO₂e" />
        <StatCard icon={Clock} label="Pending Review" color="amber"
          value={stats.pending} sub="records awaiting review" />
        <StatCard icon={AlertTriangle} label="Flagged" color="red"
          value={stats.flagged} sub="suspicious records" />
        <StatCard icon={CheckCircle} label="Approved" color="blue"
          value={stats.approved} sub={`${stats.rejected} rejected`} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Scope Pie */}
        <div className="card">
          <h3 className="font-semibold text-slate-200 mb-4 text-sm uppercase tracking-wider">Scope Breakdown</h3>
          {scopeData.length > 0 ? (
            <>
              <div className="flex justify-center">
                <PieChart width={220} height={180}>
                  <Pie data={scopeData} cx={105} cy={85} innerRadius={50} outerRadius={80}
                    paddingAngle={3} dataKey="value">
                    {scopeData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [`${(v/1000).toFixed(1)} tCO₂e`, '']}
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }} />
                </PieChart>
              </div>
              <div className="flex gap-4 justify-center mt-2">
                {scopeData.map(d => (
                  <div key={d.name} className="flex items-center gap-1.5 text-xs text-slate-400">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                    <span>{d.name}</span>
                    <span className="text-slate-300 font-medium">{(d.value/1000).toFixed(1)}t</span>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="text-slate-500 text-sm text-center py-10">No approved records yet</div>}
        </div>

        {/* Category Bar */}
        <div className="card">
          <h3 className="font-semibold text-slate-200 mb-4 text-sm uppercase tracking-wider">Top Emission Sources</h3>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={categoryData} layout="vertical" margin={{ left: 0, right: 16 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} width={110} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" fill="#22c55e" radius={[0, 4, 4, 0]} name="CO₂e" />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="text-slate-500 text-sm text-center py-10">No approved records yet</div>}
        </div>
      </div>

      {/* Recent batches */}
      <div className="card">
        <h3 className="font-semibold text-slate-200 mb-4 text-sm uppercase tracking-wider">Recent Ingestion Batches</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                <th className="pb-3 pr-4">Source</th>
                <th className="pb-3 pr-4">File</th>
                <th className="pb-3 pr-4">Rows</th>
                <th className="pb-3 pr-4">Errors</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {stats.recent_batches.map(b => (
                <tr key={b.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-3 pr-4">
                    <span className={`badge text-xs px-2 py-0.5 rounded-full font-medium`}
                      style={{ background: (batchTypeColors[b.source_type] || '#666') + '22', color: batchTypeColors[b.source_type] || '#aaa' }}>
                      {b.source_type.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-slate-400 font-mono text-xs max-w-[140px] truncate">{b.file_name}</td>
                  <td className="py-3 pr-4 text-slate-300">{b.passed_rows}</td>
                  <td className="py-3 pr-4">
                    {b.failed_rows > 0
                      ? <span className="text-red-400">{b.failed_rows}</span>
                      : <span className="text-slate-500">0</span>}
                  </td>
                  <td className="py-3 pr-4">
                    <span className={`badge ${b.status === 'completed' ? 'bg-forest-900/40 text-forest-400' : b.status === 'failed' ? 'bg-red-900/40 text-red-400' : 'bg-amber-900/40 text-amber-400'}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="py-3 text-slate-500 text-xs">{new Date(b.ingested_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
