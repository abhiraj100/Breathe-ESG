import { useEffect, useState, useCallback } from 'react';
import { records as recordsApi } from '../api';
import { CheckCircle, XCircle, Flag, ChevronDown, ChevronUp, Search, Filter, RefreshCw } from 'lucide-react';

const SCOPE_COLORS = { '1': 'text-forest-400 bg-forest-900/30', '2': 'text-blue-400 bg-blue-900/30', '3': 'text-amber-400 bg-amber-900/30' };
const STATUS_STYLES = {
  pending: 'bg-slate-800 text-slate-300',
  approved: 'bg-forest-900/30 text-forest-400',
  rejected: 'bg-red-900/30 text-red-400',
  flagged: 'bg-orange-900/30 text-orange-400',
};
const SOURCE_LABELS = { sap: 'SAP', utility_csv: 'Utility', concur_csv: 'Travel' };

function RecordRow({ rec, onAction }) {
  const [expanded, setExpanded] = useState(false);
  const [noteOpen, setNoteOpen] = useState(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);

  const act = async (action) => {
    setLoading(true);
    try {
      if (action === 'approve') await recordsApi.approve(rec.id, note);
      else if (action === 'reject') await recordsApi.reject(rec.id, note);
      else if (action === 'flag') await recordsApi.flag(rec.id, note || 'Manually flagged');
      onAction();
    } finally { setLoading(false); setNoteOpen(null); setNote(''); }
  };

  return (
    <>
      <tr className="table-row">
        <td className="py-3 pl-4 pr-2">
          <span className={`badge text-xs ${SCOPE_COLORS[rec.scope]}`}>S{rec.scope}</span>
        </td>
        <td className="py-3 pr-3 text-xs text-slate-300 max-w-[160px] truncate">{rec.category_display}</td>
        <td className="py-3 pr-3 font-mono text-xs text-slate-300">
          {Number(rec.activity_value).toLocaleString(undefined, {maximumFractionDigits: 1})} {rec.activity_unit}
        </td>
        <td className="py-3 pr-3 font-mono text-xs text-white font-medium">
          {rec.co2e_kg ? `${Number(rec.co2e_kg).toLocaleString(undefined, {maximumFractionDigits: 1})} kg` : '—'}
        </td>
        <td className="py-3 pr-3 text-xs text-slate-400 hidden md:table-cell">{rec.facility_name || '—'}</td>
        <td className="py-3 pr-3 text-xs text-slate-500 hidden lg:table-cell">{rec.period_start}</td>
        <td className="py-3 pr-3">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`badge text-xs ${STATUS_STYLES[rec.status]}`}>{rec.status_display}</span>
            {rec.is_suspicious && <span className="badge text-xs bg-orange-900/30 text-orange-400">⚠ flag</span>}
          </div>
        </td>
        <td className="py-3 pr-2">
          <span className="text-xs text-slate-500">{SOURCE_LABELS[rec.source_system] || rec.source_system}</span>
        </td>
        <td className="py-3 pr-4">
          <div className="flex items-center gap-1">
            {!rec.is_locked && rec.status === 'pending' && (
              <>
                <button onClick={() => setNoteOpen('approve')}
                  className="p-1.5 rounded-lg hover:bg-forest-900/30 text-slate-500 hover:text-forest-400 transition-colors" title="Approve">
                  <CheckCircle className="w-4 h-4" />
                </button>
                <button onClick={() => setNoteOpen('reject')}
                  className="p-1.5 rounded-lg hover:bg-red-900/20 text-slate-500 hover:text-red-400 transition-colors" title="Reject">
                  <XCircle className="w-4 h-4" />
                </button>
                <button onClick={() => setNoteOpen('flag')}
                  className="p-1.5 rounded-lg hover:bg-orange-900/20 text-slate-500 hover:text-orange-400 transition-colors" title="Flag">
                  <Flag className="w-4 h-4" />
                </button>
              </>
            )}
            <button onClick={() => setExpanded(e => !e)}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors">
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </td>
      </tr>

      {/* Note input row */}
      {noteOpen && (
        <tr className="bg-slate-900/80">
          <td colSpan={9} className="px-4 py-3">
            <div className="flex items-center gap-3">
              <input className="input flex-1 text-xs" placeholder={`Note for ${noteOpen}...`}
                value={note} onChange={e => setNote(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && act(noteOpen)} />
              <button onClick={() => act(noteOpen)} disabled={loading}
                className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  noteOpen === 'approve' ? 'bg-forest-600 hover:bg-forest-500 text-white' :
                  noteOpen === 'reject' ? 'bg-red-700 hover:bg-red-600 text-white' :
                  'bg-orange-700 hover:bg-orange-600 text-white'}`}>
                {loading ? '...' : noteOpen.charAt(0).toUpperCase() + noteOpen.slice(1)}
              </button>
              <button onClick={() => { setNoteOpen(null); setNote(''); }}
                className="text-xs text-slate-500 hover:text-slate-300">Cancel</button>
            </div>
          </td>
        </tr>
      )}

      {/* Expanded detail */}
      {expanded && (
        <tr className="bg-slate-900/50">
          <td colSpan={9} className="px-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <p className="text-slate-500 uppercase tracking-wider mb-2 font-medium">Emission Details</p>
                <dl className="space-y-1.5">
                  {[
                    ['Emission Factor', `${rec.emission_factor} kgCO₂e/${rec.activity_unit}`],
                    ['Factor Source', rec.emission_factor_source],
                    ['Source Record ID', rec.source_record_id],
                    ['Country', rec.country || '—'],
                    ['Review Notes', rec.review_notes || '—'],
                  ].map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <dt className="text-slate-500 w-36 flex-shrink-0">{k}</dt>
                      <dd className="text-slate-300 break-all">{v}</dd>
                    </div>
                  ))}
                </dl>
                {rec.is_suspicious && (
                  <div className="mt-3 bg-orange-900/20 border border-orange-800/30 rounded-lg px-3 py-2">
                    <p className="text-orange-400 font-medium mb-0.5">⚠ Suspicious</p>
                    <p className="text-orange-300/70">{rec.suspicion_reason}</p>
                  </div>
                )}
              </div>
              <div>
                <p className="text-slate-500 uppercase tracking-wider mb-2 font-medium">Raw Source Data</p>
                <pre className="bg-slate-950 rounded-lg p-3 text-[10px] text-slate-400 overflow-auto max-h-40 border border-slate-800">
                  {JSON.stringify(rec.raw_data, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function Review({ flaggedOnly = false }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    scope: '', status: flaggedOnly ? 'flagged' : 'pending', source: '', search: ''
  });
  const [selected, setSelected] = useState(new Set());
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [bulkLoading, setBulkLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) };
      if (flaggedOnly) { params.suspicious = 'true'; delete params.status; }
      const res = await recordsApi.list(params);
      setData(res.data.results || res.data);
      setTotalPages(Math.ceil((res.data.count || (res.data.results || res.data).length) / 50));
    } finally { setLoading(false); }
  }, [filters, page, flaggedOnly]);

  useEffect(() => { fetch(); }, [fetch]);

  const bulkApprove = async () => {
    if (!selected.size) return;
    setBulkLoading(true);
    try {
      await recordsApi.bulkApprove([...selected]);
      setSelected(new Set());
      fetch();
    } finally { setBulkLoading(false); }
  };

  const toggleAll = () => {
    if (selected.size === data.length) setSelected(new Set());
    else setSelected(new Set(data.filter(r => !r.is_locked && r.status === 'pending').map(r => r.id)));
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-white">
            {flaggedOnly ? 'Flagged Records' : 'Review Records'}
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {flaggedOnly ? 'Records with suspicious values requiring attention' : 'Approve or reject emission records before audit lock'}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {selected.size > 0 && (
            <button onClick={bulkApprove} disabled={bulkLoading} className="btn-primary flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              Approve {selected.size} selected
            </button>
          )}
          <button onClick={fetch} className="btn-secondary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[160px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input className="input pl-8 text-xs" placeholder="Search facility, category..."
              value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} />
          </div>
          {!flaggedOnly && (
            <select className="input text-xs w-auto min-w-[120px]" value={filters.status}
              onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}>
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="flagged">Flagged</option>
            </select>
          )}
          <select className="input text-xs w-auto min-w-[100px]" value={filters.scope}
            onChange={e => setFilters(f => ({ ...f, scope: e.target.value }))}>
            <option value="">All Scopes</option>
            <option value="1">Scope 1</option>
            <option value="2">Scope 2</option>
            <option value="3">Scope 3</option>
          </select>
          <select className="input text-xs w-auto min-w-[110px]" value={filters.source}
            onChange={e => setFilters(f => ({ ...f, source: e.target.value }))}>
            <option value="">All Sources</option>
            <option value="sap">SAP</option>
            <option value="utility_csv">Utility</option>
            <option value="concur_csv">Travel</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800 bg-slate-900/80">
                <th className="pl-4 pr-2 py-3">
                  <input type="checkbox" className="rounded" checked={selected.size > 0 && selected.size === data.filter(r => !r.is_locked && r.status === 'pending').length}
                    onChange={toggleAll} />
                </th>
                <th className="py-3 pr-3">Scope</th>
                <th className="py-3 pr-3">Category</th>
                <th className="py-3 pr-3">Activity</th>
                <th className="py-3 pr-3">CO₂e</th>
                <th className="py-3 pr-3 hidden md:table-cell">Facility</th>
                <th className="py-3 pr-3 hidden lg:table-cell">Period</th>
                <th className="py-3 pr-3">Status</th>
                <th className="py-3 pr-3">Source</th>
                <th className="py-3 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-center py-12 text-slate-500">Loading records...</td></tr>
              ) : data.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-12 text-slate-500">No records match your filters</td></tr>
              ) : data.map(rec => (
                <RecordRow key={rec.id} rec={rec} onAction={fetch} />
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800">
            <span className="text-xs text-slate-500">Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary text-xs py-1.5 px-3">Prev</button>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary text-xs py-1.5 px-3">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
