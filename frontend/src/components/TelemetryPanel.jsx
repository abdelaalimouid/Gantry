import { motion } from "framer-motion";
import { Activity, Database } from "lucide-react";

/* ── Radial Gauge ─────────────────────────────────────────────────────────── */
function Gauge({ label, value, max, unit, color = "#06b6d4", icon }) {
  const pct = Math.min(value / max, 1);
  const circumference = 2 * Math.PI * 54;
  const offset = circumference * (1 - pct * 0.75);          // 270° arc
  const glowClass = color === "#ef4444" ? "glow-red" : "glow-green";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 120 120" className={`w-full h-full ${glowClass}`}>
          {/* Track */}
          <circle
            cx="60" cy="60" r="54"
            fill="none"
            stroke="#1e293b"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * 0.25}
            strokeLinecap="round"
            transform="rotate(135 60 60)"
          />
          {/* Value arc */}
          <motion.circle
            cx="60" cy="60" r="54"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeLinecap="round"
            transform="rotate(135 60 60)"
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold" style={{ color }}>
            {typeof value === "number"
              ? (value >= 1 ? value.toFixed(value >= 100 ? 0 : 1) : value.toFixed(4))
              : value}
          </span>
          <span className="text-[10px] text-slate-400 uppercase tracking-wider">{unit}</span>
        </div>
      </div>
      <div className="flex items-center gap-1 text-xs text-slate-400">
        {icon}
        <span>{label}</span>
      </div>
    </div>
  );
}

/* ── Panel ────────────────────────────────────────────────────────────────── */
export default function TelemetryPanel({ data, live }) {
  // Prefer live WS values, fall back to orchestration snapshot
  const rul       = live?.rul       ?? data?.physical_metrics?.rul ?? 0;
  const vibration = live?.vibration ?? data?.physical_metrics?.vibration ?? 0;
  const volume    = data?.physical_metrics?.data_volume ?? "—";
  const cycle     = live?.cycle     ?? null;

  // Dynamic scaling — adapt to real NASA data ranges
  const rulMax = Math.max(200, rul * 1.2);
  const vibMax = Math.max(0.30, vibration * 1.3);

  const rulColor = rul < 10 ? "#ef4444" : rul < 30 ? "#f59e0b" : "#22c55e";
  // NASA S11 normal range ≈ 0.23–0.25; only flag truly abnormal spikes
  const vibColor = vibration > 0.35 ? "#ef4444" : vibration > 0.28 ? "#f59e0b" : "#22c55e";

  return (
    <motion.section
      initial={{ opacity: 0, x: -30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
      className="bg-panel border border-border rounded-xl p-5 flex flex-col gap-6"
    >
      <h2 className="text-xs font-bold tracking-widest text-slate-400 uppercase flex items-center gap-2">
        <Activity size={14} className="text-accent" />
        Physical Telemetry
      </h2>

      <div className="flex flex-col items-center gap-6 flex-1 justify-center">
        <Gauge
          label="Remaining Useful Life"
          value={rul}
          max={rulMax}
          unit="cycles"
          color={rulColor}
          icon={<Activity size={11} />}
        />
        <Gauge
          label="Vibration — Sensor S11"
          value={vibration}
          max={vibMax}
          unit="g RMS"
          color={vibColor}
          icon={<Activity size={11} />}
        />
      </div>

      {/* Data volume badge */}
      <div className="mt-auto bg-midnight/60 rounded-lg border border-border px-4 py-3 flex items-center gap-2">
        <Database size={14} className="text-cyan-400" />
        <div>
          <p className="text-[11px] font-semibold text-cyan-400">Data Volume</p>
          <p className="text-[10px] text-slate-400">{volume}</p>
        </div>
      </div>

      {/* Live cycle indicator */}
      {cycle !== null && (
        <div className="bg-midnight/60 rounded-lg border border-emerald-700/30 px-4 py-3 flex items-center gap-2">
          <Activity size={14} className="text-emerald-400 animate-pulse" />
          <div>
            <p className="text-[11px] font-semibold text-emerald-400">Live Cycle</p>
            <p className="text-[10px] text-slate-400">Cycle {cycle} — streaming every 5 s</p>
          </div>
        </div>
      )}
    </motion.section>
  );
}
