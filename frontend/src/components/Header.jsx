import { useState, useEffect, useRef } from "react";
import { Activity, Zap, Eye, ChevronDown, Radio } from "lucide-react";

const API_BASE = "/api";

export default function Header({ unitId, setUnitId, onRun, loading, judgingMode, setJudging }) {
  const [units, setUnits]       = useState([]);
  const [open, setOpen]         = useState(false);
  const [fetching, setFetching] = useState(false);
  const dropRef = useRef(null);

  // Fetch unit list on mount + every 30s
  useEffect(() => {
    const load = async () => {
      setFetching(true);
      try {
        const res = await fetch(`${API_BASE}/units`);
        if (res.ok) {
          const data = await res.json();
          setUnits(data.units || []);
        }
      } catch { /* silent */ }
      setFetching(false);
    };
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => { if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selected = units.find((u) => u.unit_id === unitId);

  return (
    <header className="border-b border-border bg-panel/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="flex items-center justify-between px-6 py-3">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <Activity size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wider text-white">GANTRY 3.0</h1>
            <p className="text-[10px] text-slate-400 tracking-widest">DIGITAL TWIN COMMAND CENTER</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {/* Judging Mode toggle */}
          <button
            onClick={() => setJudging(!judgingMode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-semibold border transition-all duration-300 ${
              judgingMode
                ? "bg-amber-500/20 border-amber-500 text-amber-400"
                : "bg-panel border-border text-slate-400 hover:border-slate-500"
            }`}
          >
            <Eye size={13} />
            Judging Mode
          </button>

          {/* Unit Selector Dropdown */}
          <div ref={dropRef} className="relative">
            <button
              onClick={() => setOpen(!open)}
              className="flex items-center gap-2 bg-midnight border border-border rounded px-3 py-1.5 text-xs text-slate-300 w-64 hover:border-accent focus:border-accent focus:outline-none transition-colors"
            >
              {selected?.active && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
              )}
              {!selected && unitId && (
                <Radio size={11} className="text-slate-500 flex-shrink-0" />
              )}
              <span className="flex-1 text-left truncate">{unitId || "Select Unit…"}</span>
              <ChevronDown size={13} className={`text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
            </button>

            {open && (
              <div className="absolute top-full mt-1 left-0 w-72 bg-panel border border-border rounded-lg shadow-2xl z-50 max-h-64 overflow-y-auto">
                {units.length === 0 && (
                  <div className="px-4 py-3 text-[11px] text-slate-500 italic">
                    {fetching ? "Loading units…" : "No units found in Elasticsearch"}
                  </div>
                )}
                {units.map((u) => (
                  <button
                    key={u.unit_id}
                    onClick={() => { setUnitId(u.unit_id); setOpen(false); }}
                    className={`w-full flex items-center gap-2.5 px-4 py-2.5 hover:bg-midnight/80 transition-colors text-left border-b border-border/50 last:border-b-0 ${
                      u.unit_id === unitId ? "bg-cyan-900/20" : ""
                    }`}
                  >
                    {/* Activity dot */}
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      u.active ? "bg-emerald-400 animate-pulse" : "bg-slate-600"
                    }`} />
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className={`text-[11px] font-semibold truncate ${
                        u.unit_id === unitId ? "text-cyan-300" : "text-slate-300"
                      }`}>
                        {u.unit_id}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {u.doc_count} docs · Cycle {u.cycle ?? "?"} · RUL {u.rul ?? "?"}
                      </p>
                    </div>
                    {/* Active badge */}
                    {u.active && (
                      <span className="text-[9px] font-bold text-emerald-400 bg-emerald-900/30 border border-emerald-700/40 rounded px-1.5 py-0.5 uppercase tracking-wider">
                        Live
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Run button */}
          <button
            onClick={onRun}
            disabled={loading}
            className="flex items-center gap-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 text-white text-xs font-bold px-5 py-2 rounded transition-all duration-300"
          >
            <Zap size={14} className={loading ? "animate-spin" : ""} />
            {loading ? "RUNNING…" : "ORCHESTRATE"}
          </button>
        </div>
      </div>
    </header>
  );
}
