import { motion } from "framer-motion";
import { Cpu, Loader2 } from "lucide-react";

/* Color map for crane status */
const STATUS_COLORS = {
  CRITICAL: { stroke: "#ef4444", glow: "0 0 40px #ef4444", label: "CRITICAL FAILURE" },
  WARNING:  { stroke: "#f59e0b", glow: "0 0 30px #f59e0b", label: "DRL VETO — COST RISK" },
  HEALTHY:  { stroke: "#22c55e", glow: "0 0 24px #16a34a", label: "SYSTEMS NOMINAL" },
  IDLE:     { stroke: "#22c55e", glow: "0 0 18px #16a34a", label: "AWAITING COMMAND" },
};

/**
 * Derive the visual state for the crane.
 * Goes red ONLY when `failureActive` is true (set by trigger_failure.py alert).
 * Otherwise follows the orchestration-derived `status`.
 */
function resolveTelemetryColor(status, failureActive) {
  if (failureActive) return { ...STATUS_COLORS.CRITICAL, telemetryCritical: true };
  return { ...(STATUS_COLORS[status] || STATUS_COLORS.IDLE), telemetryCritical: false };
}

/* ── Interactive SVG Crane ────────────────────────────────────────────────── */
function CraneSVG({ status, failureActive }) {
  const c = resolveTelemetryColor(status, failureActive);

  return (
    <svg viewBox="0 0 320 320" className="w-full max-w-xs mx-auto">
      {/* Glow filter */}
      <defs>
        <filter id="crane-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Base platform */}
      <rect x="100" y="270" width="120" height="20" rx="4" fill="#1e293b" stroke={c.stroke} strokeWidth="1.5" />

      {/* Vertical mast */}
      <motion.rect
        x="150" y="60" width="20" height="210" rx="3"
        fill="#0f172a"
        stroke={c.stroke}
        strokeWidth="2"
        filter="url(#crane-glow)"
        animate={{ stroke: c.stroke }}
        transition={{ duration: 0.6 }}
      />

      {/* Horizontal boom */}
      <motion.rect
        x="60" y="55" width="200" height="14" rx="3"
        fill="#0f172a"
        stroke={c.stroke}
        strokeWidth="2"
        filter="url(#crane-glow)"
        animate={{ stroke: c.stroke }}
        transition={{ duration: 0.6 }}
      />

      {/* Diagonal brace */}
      <motion.line
        x1="170" y1="69" x2="240" y2="150"
        stroke={c.stroke}
        strokeWidth="2"
        strokeLinecap="round"
        animate={{ stroke: c.stroke }}
        transition={{ duration: 0.6 }}
      />

      {/* Cable */}
      <motion.line
        x1="100" y1="69" x2="100" y2="200"
        stroke={c.stroke}
        strokeWidth="1.5"
        strokeDasharray="6 4"
        animate={{ stroke: c.stroke, y2: (status === "CRITICAL" || c.telemetryCritical) ? 220 : 200 }}
        transition={{ duration: 1, repeat: (status === "CRITICAL" || c.telemetryCritical) ? Infinity : 0, repeatType: "reverse" }}
      />

      {/* Hook block */}
      <motion.rect
        x="88" y="198" width="24" height="18" rx="4"
        fill={c.stroke}
        animate={{
          y: (status === "CRITICAL" || c.telemetryCritical) ? 218 : 198,
          fill: c.stroke,
        }}
        transition={{ duration: 1, repeat: (status === "CRITICAL" || c.telemetryCritical) ? Infinity : 0, repeatType: "reverse" }}
      />

      {/* Pulse ring (critical / telemetry-critical / warning) */}
      {(status === "CRITICAL" || status === "WARNING" || c.telemetryCritical) && (
        <motion.circle
          cx="160" cy="160" r="90"
          fill="none"
          stroke={c.stroke}
          strokeWidth={c.telemetryCritical ? "2" : "1"}
          initial={{ r: 60, opacity: 0.7 }}
          animate={{ r: 130, opacity: 0 }}
          transition={{ duration: c.telemetryCritical ? 1.2 : 2, repeat: Infinity, ease: "easeOut" }}
        />
      )}

      {/* Second faster pulse ring when telemetry-critical */}
      {c.telemetryCritical && (
        <motion.circle
          cx="160" cy="160" r="90"
          fill="none"
          stroke="#ef4444"
          strokeWidth="1"
          initial={{ r: 80, opacity: 0.5 }}
          animate={{ r: 140, opacity: 0 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut", delay: 0.4 }}
        />
      )}

      {/* Cabin window */}
      <rect x="153" y="80" width="14" height="14" rx="2" fill={c.stroke} opacity="0.25" />

      {/* Status indicator LEDs */}
      <circle cx="145" cy="50" r="4" fill={c.stroke} opacity="0.9" />
      <circle cx="160" cy="50" r="4" fill={c.stroke} opacity="0.6" />
      <circle cx="175" cy="50" r="4" fill={c.stroke} opacity="0.3" />
    </svg>
  );
}

/* ── Panel ────────────────────────────────────────────────────────────────── */
export default function DigitalTwin({ status, data, loading, live, failureActive }) {
  const c = resolveTelemetryColor(status, failureActive);

  return (
    <motion.section
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className="bg-panel border border-border rounded-xl p-5 flex flex-col items-center gap-4"
    >
      <h2 className="text-xs font-bold tracking-widest text-slate-400 uppercase flex items-center gap-2">
        <Cpu size={14} className="text-accent" />
        Digital Twin Canvas
      </h2>

      {/* Crane */}
      <div className={`flex-1 flex items-center justify-center w-full transition-all duration-500 ${
        c.telemetryCritical ? "crane-pulse-red" : ""
      }`}>
        {loading ? (
          <Loader2 size={48} className="text-accent animate-spin" />
        ) : (
          <CraneSVG status={status} failureActive={failureActive} />
        )}
      </div>

      {/* Peak telemetry indicators when failure active */}
      {c.telemetryCritical && live && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full grid grid-cols-2 gap-2"
        >
          <div className="bg-red-950/40 border border-red-700/50 rounded-lg px-3 py-2 text-center">
            <p className="text-[9px] text-red-400/80 uppercase tracking-widest">Peak RUL</p>
            <p className="text-lg font-bold text-red-300 animate-pulse">
              {typeof live.rul === "number" ? live.rul.toFixed(1) : live.rul}
            </p>
          </div>
          <div className="bg-red-950/40 border border-red-700/50 rounded-lg px-3 py-2 text-center">
            <p className="text-[9px] text-red-400/80 uppercase tracking-widest">Peak Vibration</p>
            <p className="text-lg font-bold text-red-300 animate-pulse">
              {typeof live.vibration === "number" ? live.vibration.toFixed(4) : live.vibration}
            </p>
          </div>
        </motion.div>
      )}

      {/* Status badge */}
      <motion.div
        key={`${status}-${c.telemetryCritical}`}
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="px-5 py-2 rounded-full text-xs font-bold tracking-widest border"
        style={{
          color: c.stroke,
          borderColor: c.stroke,
          boxShadow: c.glow,
          background: `${c.stroke}10`,
        }}
      >
        {c.telemetryCritical ? "CRITICAL FAILURE" : c.label}
      </motion.div>

      {/* DRL Decision card */}
      {data?.drl_decision && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="w-full bg-midnight/60 rounded-lg border border-border p-4 text-center"
        >
          <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">DRL Decision</p>
          <p
            className="text-sm font-bold tracking-wider"
            style={{ color: data.drl_decision.action === 1 ? "#22d3ee" : "#f59e0b" }}
          >
            {data.drl_decision.label?.replace(/_/g, " ")}
          </p>
        </motion.div>
      )}
    </motion.section>
  );
}
