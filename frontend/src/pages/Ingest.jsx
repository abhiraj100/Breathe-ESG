import { useState, useRef } from 'react';
import { ingest } from '../api';
import { Upload, CheckCircle2, XCircle, AlertCircle, FileText, Zap, Plug, Plane } from 'lucide-react';

const SOURCES = [
  {
    id: 'sap',
    label: 'SAP Fuel & Procurement',
    icon: Zap,
    scope: 'Scope 1 + Scope 3',
    description: 'IDoc-derived semicolon-delimited flat file. Handles German column headers (MENGE, BUDAT, WERKS), plant codes, multi-format dates (YYYYMMDD, DD.MM.YYYY), mixed fuel/procurement rows.',
    color: 'forest',
    accepts: '.csv,.txt',
    sampleRow: 'BELNR;BUDAT;WERKS;MATNR;MATNR_DESC;MENGE;MEINS;DMBTR;WAERS;KOSTL',
  },
  {
    id: 'utility',
    label: 'Utility (Electricity)',
    icon: Plug,
    scope: 'Scope 2',
    description: 'Portal CSV export from facilities team. Handles kWh/MWh units, billing periods that don\'t align with calendar months, multiple meters per facility, tariff codes.',
    color: 'blue',
    accepts: '.csv',
    sampleRow: 'METER_ID,FACILITY,BILLING_START,BILLING_END,CONSUMPTION,UNIT,TARIFF,AMOUNT',
  },
  {
    id: 'travel',
    label: 'Corporate Travel',
    icon: Plane,
    scope: 'Scope 3',
    description: 'Concur-style CSV with trip segments (air/hotel/ground). Infers distance from airport codes when missing, applies cabin-class-specific emission factors.',
    color: 'amber',
    accepts: '.csv',
    sampleRow: 'TRIP_ID,EMPLOYEE,SEGMENT_TYPE,ORIGIN,DESTINATION,TRAVEL_DATE,NIGHTS,CABIN_CLASS',
  },
];

function DropZone({ source, onResult }) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState(null); // null | 'loading' | {ok, data} | {error}
  const inputRef = useRef();

  const colorMap = {
    forest: { border: 'border-forest-600/40 hover:border-forest-500', bg: 'bg-forest-600/5', icon: 'text-forest-400', badge: 'bg-forest-900/30 text-forest-400' },
    blue: { border: 'border-blue-600/40 hover:border-blue-500', bg: 'bg-blue-600/5', icon: 'text-blue-400', badge: 'bg-blue-900/30 text-blue-400' },
    amber: { border: 'border-amber-600/40 hover:border-amber-500', bg: 'bg-amber-600/5', icon: 'text-amber-400', badge: 'bg-amber-900/30 text-amber-400' },
  };
  const c = colorMap[source.color];
  const Icon = source.icon;

  const upload = async (file) => {
    setStatus('loading');
    try {
      const res = await ingest[source.id](file);
      setStatus({ ok: true, data: res.data });
      onResult(res.data);
    } catch (e) {
      setStatus({ error: e.response?.data?.error || 'Upload failed' });
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) upload(file);
  };

  return (
    <div className="card space-y-4">
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${c.badge}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white text-sm">{source.label}</h3>
          <span className={`text-xs ${c.icon}`}>{source.scope}</span>
          <p className="text-slate-400 text-xs mt-1 leading-relaxed">{source.description}</p>
        </div>
      </div>

      {/* Sample header */}
      <div className="bg-slate-950 rounded-lg p-3 font-mono text-xs text-slate-400 overflow-x-auto whitespace-nowrap border border-slate-800">
        {source.sampleRow}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          dragging ? `${c.border} ${c.bg}` : `border-slate-700 hover:border-slate-600`
        }`}
      >
        <input ref={inputRef} type="file" accept={source.accepts} className="hidden"
          onChange={e => e.target.files[0] && upload(e.target.files[0])} />
        <Upload className="w-6 h-6 text-slate-500 mx-auto mb-2" />
        <p className="text-sm text-slate-400">Drop CSV here or <span className={`${c.icon} font-medium`}>click to browse</span></p>
        <p className="text-xs text-slate-600 mt-1">{source.accepts}</p>
      </div>

      {/* Result */}
      {status === 'loading' && (
        <div className="flex items-center gap-2 text-sm text-slate-400 bg-slate-800 rounded-lg px-4 py-3">
          <div className="w-4 h-4 border-2 border-slate-600 border-t-forest-400 rounded-full animate-spin" />
          Processing...
        </div>
      )}
      {status?.ok && (
        <div className="bg-forest-900/20 border border-forest-800/40 rounded-lg px-4 py-3 text-sm">
          <div className="flex items-center gap-2 text-forest-400 font-medium mb-1">
            <CheckCircle2 className="w-4 h-4" />Ingested successfully
          </div>
          <div className="text-slate-400 text-xs space-y-0.5">
            <p>{status.data.passed_rows} records imported • {status.data.failed_rows} parsing errors</p>
            <p className="font-mono text-slate-500">{status.data.file_name}</p>
          </div>
        </div>
      )}
      {status?.error && (
        <div className="bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-3 text-sm">
          <div className="flex items-center gap-2 text-red-400 font-medium mb-1">
            <XCircle className="w-4 h-4" />Upload failed
          </div>
          <p className="text-red-300/70 text-xs">{status.error}</p>
        </div>
      )}
    </div>
  );
}

export default function Ingest({ onIngested }) {
  const [results, setResults] = useState([]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-white">Ingest Data</h1>
        <p className="text-slate-400 text-sm mt-1">Upload files from your three data sources. Records go into Pending Review automatically.</p>
      </div>

      <div className="bg-amber-900/10 border border-amber-800/30 rounded-xl px-4 py-3 flex gap-3">
        <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-300/80 leading-relaxed">
          <strong>Tip:</strong> Download the sample CSV files from the repo's <code className="font-mono bg-amber-900/30 px-1 rounded">sample_data/</code> folder to test ingestion.
          All records land in <strong>Pending</strong> status — go to Review Records to approve them.
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {SOURCES.map(s => (
          <DropZone key={s.id} source={s} onResult={d => { setResults(r => [d, ...r]); onIngested?.(); }} />
        ))}
      </div>
    </div>
  );
}
