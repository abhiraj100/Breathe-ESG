import { useEffect, useState } from 'react';
import { batches as batchesApi } from '../api';
import { Package, AlertCircle } from 'lucide-react';

const SOURCE_COLORS = { sap: '#22c55e', utility: '#3b82f6', travel: '#f59e0b' };

export default function Batches() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    batchesApi.list().then(r => { setData(r.data.results || r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const viewErrors = async (batch) => {
    setSelected(batch);
    const res = await batchesApi.errors(batch.id);
    setErrors(res.data);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-white">Batch History</h1>
        <p className="text-slate-400 text-sm mt-1">All ingestion runs and their parsing results</p>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800 bg-slate-900/80">
                <th className="pl-4 py-3 pr-3">Source</th>
                <th className="py-3 pr-3">File</th>
                <th className="py-3 pr-3">Total</th>
                <th className="py-3 pr-3">Passed</th>
                <th className="py-3 pr-3">Errors</th>
                <th className="py-3 pr-3">Status</th>
                <th className="py-3 pr-3">Ingested By</th>
                <th className="py-3 pr-4">Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-center py-10 text-slate-500">Loading...</td></tr>
              ) : data.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-10 text-slate-500">No batches yet. Ingest some data first.</td></tr>
              ) : data.map(b => (
                <tr key={b.id} className="table-row cursor-pointer" onClick={() => b.failed_rows > 0 && viewErrors(b)}>
                  <td className="py-3 pl-4 pr-3">
                    <span className="badge text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ background: (SOURCE_COLORS[b.source_type] || '#666') + '22', color: SOURCE_COLORS[b.source_type] || '#aaa' }}>
                      {b.source_type_display}
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-mono text-xs text-slate-400 max-w-[180px] truncate">{b.file_name}</td>
                  <td className="py-3 pr-3 text-slate-300">{b.total_rows}</td>
                  <td className="py-3 pr-3 text-forest-400">{b.passed_rows}</td>
                  <td className="py-3 pr-3">
                    {b.failed_rows > 0
                      ? <span className="text-red-400 flex items-center gap-1 cursor-pointer"><AlertCircle className="w-3.5 h-3.5" />{b.failed_rows}</span>
                      : <span className="text-slate-600">0</span>}
                  </td>
                  <td className="py-3 pr-3">
                    <span className={`badge text-xs ${b.status === 'completed' ? 'bg-forest-900/30 text-forest-400' : b.status === 'failed' ? 'bg-red-900/30 text-red-400' : 'bg-amber-900/30 text-amber-400'}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="py-3 pr-3 text-slate-400 text-xs">{b.ingested_by_name}</td>
                  <td className="py-3 pr-4 text-slate-500 text-xs">{new Date(b.ingested_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Error modal */}
      {selected && errors && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={() => { setSelected(null); setErrors(null); }}>
          <div className="card w-full max-w-2xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white">Parse Errors — {selected.file_name}</h3>
              <button onClick={() => { setSelected(null); setErrors(null); }} className="text-slate-400 hover:text-white text-lg">×</button>
            </div>
            {errors.length === 0 ? (
              <p className="text-slate-400 text-sm">No errors recorded.</p>
            ) : (
              <div className="space-y-3">
                {errors.map((e, i) => (
                  <div key={i} className="bg-red-900/10 border border-red-900/30 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-red-400 text-xs font-medium mb-1">
                      <AlertCircle className="w-3.5 h-3.5" />Row {e.row_number}: {e.error_message}
                    </div>
                    <pre className="text-[10px] text-slate-400 overflow-auto bg-slate-950 rounded p-2 max-h-24">
                      {JSON.stringify(e.raw_row, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
