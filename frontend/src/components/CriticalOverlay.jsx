import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, X, Activity, Radio, CheckCircle2, Brain, User, Layers, ShieldCheck, DollarSign, Clock, TrendingDown } from "lucide-react";

/**
 * CriticalOverlay – full-screen high-priority modal that appears whenever
 * the WebSocket reports unit_status === "CRITICAL" or isError === true.
 *
 * Shows live telemetry snapshot + the agent-proposed solution as it arrives.
 */
export default function CriticalOverlay({ visible, telemetry, agentSolution, streamingLogs, onDismiss, onOrchestrate }) {
  const rul       = telemetry?.rul       ?? "—";
  const vibration = telemetry?.vibration ?? "—";
  const unitId    = telemetry?.unit_id   ?? "UNKNOWN";
  const cycle     = telemetry?.cycle     ?? "—";

  const decision  = agentSolution?.decision ?? null;
  const solving   = streamingLogs?.length > 0 && !decision;
  const costComp  = decision?.cost_comparison ?? null;

  // ── Live downtime counter ────────────────────────────────────────
  const [downtime, setDowntime] = useState(0);
  useEffect(() => {
    if (!visible) { setDowntime(0); return; }
    const start = Date.now();
    const iv = setInterval(() => setDowntime(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(iv);
  }, [visible]);

  const fmtTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec.toString().padStart(2, "0")}s` : `${sec}s`;
  };

  // ── Accept solution → resume system ──────────────────────────────
  const handleAccept = async () => {
    try {
      const res = await fetch("/api/system-resume", { method: "POST" });
      if (!res.ok) console.error("[handleAccept] system-resume failed:", res.status, await res.text());
    } catch (err) {
      console.error("[handleAccept] system-resume error:", err);
    }
    onDismiss();
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="critical-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-[100] flex items-center justify-center"
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

          {/* Pulsing border ring behind the card */}
          <motion.div
            className={`absolute rounded-2xl border-2 ${
              decision ? "w-[920px] h-[780px] border-emerald-500/60" : "w-[700px] h-[540px] border-red-500/60"
            }`}
            animate={{ scale: [1, 1.04, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />

          {/* Card */}
          <motion.div
            initial={{ scale: 0.85, opacity: 0, y: 30 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: "spring", stiffness: 260, damping: 22 }}
            className={`relative z-10 max-w-[96vw] border rounded-2xl shadow-lg overflow-hidden max-h-[92vh] overflow-y-auto ${
              decision
                ? "w-[900px] bg-gradient-to-b from-emerald-950/90 to-[#0f172a] border-emerald-600/70 shadow-[0_0_80px_rgba(16,185,129,0.25)]"
                : "w-[680px] bg-gradient-to-b from-red-950/90 to-[#0f172a] border-red-600/70 shadow-[0_0_80px_rgba(239,68,68,0.35)]"
            }`}
          >
            {/* Scanline decorative bar */}
            <div className={`h-1 w-full animate-pulse ${
              decision
                ? "bg-gradient-to-r from-emerald-600 via-emerald-400 to-emerald-600"
                : "bg-gradient-to-r from-red-600 via-red-400 to-red-600"
            }`} />

            {/* Header */}
            <div className="flex items-center justify-between px-8 pt-6 pb-4">
              <div className="flex items-center gap-4">
                {decision ? (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <ShieldCheck size={36} className="text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                  </motion.div>
                ) : (
                  <motion.div
                    animate={{ rotate: [0, 10, -10, 0] }}
                    transition={{ duration: 0.6, repeat: Infinity, repeatDelay: 1.5 }}
                  >
                    <AlertTriangle size={36} className="text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
                  </motion.div>
                )}
                <div>
                  <h2 className={`text-xl font-bold tracking-widest uppercase ${
                    decision ? "text-emerald-300" : "text-red-300"
                  }`}>
                    {decision ? "Agent Solution Ready" : "Critical State"}
                  </h2>
                  <p className={`text-xs tracking-wider mt-0.5 ${
                    decision ? "text-emerald-400/80" : "text-red-400/80"
                  }`}>
                    {decision ? "MCP AGENT SWARM — PROPOSED FIX" : solving ? "AGENTS ANALYZING…" : "AUTONOMOUS SYSTEM RESPONSE REQUIRED"}
                  </p>
                </div>
              </div>
              <button
                onClick={onDismiss}
                className={`p-2 rounded-lg transition-colors ${
                  decision ? "hover:bg-emerald-900/40" : "hover:bg-red-900/40"
                }`}
                aria-label="Dismiss"
              >
                <X size={22} className={decision ? "text-emerald-400" : "text-red-400"} />
              </button>
            </div>

            {/* Telemetry snapshot */}
            <div className="px-8 pb-5 grid grid-cols-3 gap-4">
              <TelemetryCard
                label="Unit"
                value={unitId}
                icon={<Radio size={14} className={decision ? "text-emerald-400" : "text-red-400"} />}
                accent={decision ? "emerald" : "red"}
              />
              <TelemetryCard
                label="RUL"
                value={typeof rul === "number" ? rul.toFixed(1) : rul}
                sub="cycles"
                icon={<Activity size={14} className={decision ? "text-emerald-400" : "text-red-400"} />}
                critical={typeof rul === "number" && rul < 1}
                accent={decision ? "emerald" : "red"}
              />
              <TelemetryCard
                label="Vibration"
                value={typeof vibration === "number" ? vibration.toFixed(4) : vibration}
                sub="g RMS"
                icon={<Activity size={14} className={decision ? "text-emerald-400" : "text-red-400"} />}
                critical={typeof vibration === "number" && vibration > 0.08}
                accent={decision ? "emerald" : "red"}
              />
            </div>

            {/* ── Live Agent Steps (while solving) ──────────────────── */}
            {solving && streamingLogs?.length > 0 && (
              <div className="px-8 pb-5">
                <div className="bg-midnight/60 border border-amber-700/30 rounded-xl p-4 space-y-3 max-h-64 overflow-y-auto">
                  <p className="text-[11px] text-amber-400/80 uppercase tracking-widest font-semibold flex items-center gap-1.5">
                    <Brain size={12} /> Agent Swarm — Live
                    <span className="ml-auto inline-flex h-2.5 w-2.5 rounded-full bg-amber-400 animate-pulse" />
                  </p>
                  {streamingLogs.map((log) => (
                    <motion.div
                      key={log.step}
                      initial={{ opacity: 0, x: 12 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-2.5"
                    >
                      <StepIcon agent={log.agent} />
                      <div>
                        <span className="text-xs font-bold text-slate-300">{log.agent}</span>
                        <p className="text-xs text-slate-400 leading-snug">{log.event}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Agent Solution Card ───────────────────────────────── */}
            {decision && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="px-8 pb-5 space-y-4"
              >
                {/* DRL Decision */}
                <div className={`rounded-xl border p-5 ${
                  decision.drl_decision?.action === 1
                    ? "bg-emerald-950/40 border-emerald-600/50"
                    : "bg-amber-950/40 border-amber-600/50"
                }`}>
                  <div className="flex items-center gap-2 mb-3">
                    <Brain size={18} className={
                      decision.drl_decision?.action === 1 ? "text-emerald-400" : "text-amber-400"
                    } />
                    <span className="text-xs font-bold uppercase tracking-widest text-slate-300">
                      DRL Policy Decision
                    </span>
                  </div>
                  <p className={`text-lg font-bold tracking-wider mb-2 ${
                    decision.drl_decision?.action === 1 ? "text-emerald-300" : "text-amber-300"
                  }`}>
                    {decision.drl_decision?.label?.replace(/_/g, " ")}
                  </p>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    {decision.drl_decision?.reason}
                  </p>
                </div>

                {/* Shadow Model conflict */}
                {decision.shadow_model?.conflict && (
                  <div className="rounded-xl border border-orange-600/40 bg-orange-950/30 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Layers size={16} className="text-orange-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-orange-400">
                        Shadow Model Conflict
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="bg-midnight/50 rounded-lg px-3 py-2">
                        <span className="text-slate-500">Standard Rule:</span>{" "}
                        <span className="font-bold text-slate-300">{decision.shadow_model.simple_rule?.decision}</span>
                      </div>
                      <div className="bg-purple-950/30 rounded-lg px-3 py-2">
                        <span className="text-slate-500">DRL Policy:</span>{" "}
                        <span className="font-bold text-purple-300">{decision.shadow_model.drl_policy?.decision}</span>
                      </div>
                    </div>
                    <p className="text-sm text-amber-300 mt-2 font-semibold">
                      Verdict: {decision.shadow_model.enterprise_verdict}
                      {decision.shadow_model.cost_saved > 0 &&
                        ` — $${decision.shadow_model.cost_saved?.toFixed(0)} saved`
                      }
                    </p>
                  </div>
                )}

                {/* Personnel */}
                <div className="rounded-xl border border-border bg-midnight/50 p-4 flex items-center gap-3">
                  <User size={18} className="text-emerald-400" />
                  <div>
                    <span className="text-sm font-bold text-slate-300">Technician Status: </span>
                    <span className={`text-sm font-bold ${
                      decision.personnel?.available ? "text-emerald-400" : "text-red-400"
                    }`}>
                      {decision.personnel?.available ? "Available" : "Unavailable"}
                    </span>
                    <span className="text-sm text-slate-500">
                      {" — "}{decision.personnel?.hours_until_shift_end?.toFixed(1)}h remaining
                    </span>
                  </div>
                </div>

                {/* ── Cost Comparison Panel ──────────────────────────── */}
                {costComp && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-4 space-y-3"
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <DollarSign size={18} className="text-emerald-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-emerald-300">
                        Maintenance Strategy Comparison
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      {/* Reactive */}
                      <CostCard
                        label={costComp.reactive?.label}
                        cost={costComp.reactive?.cost}
                        hours={costComp.reactive?.downtime_hours}
                        desc={costComp.reactive?.description}
                        color="red"
                      />
                      {/* Preventive */}
                      <CostCard
                        label={costComp.preventive?.label}
                        cost={costComp.preventive?.cost}
                        hours={costComp.preventive?.downtime_hours}
                        desc={costComp.preventive?.description}
                        color="amber"
                      />
                      {/* Predictive (Gantry) */}
                      <CostCard
                        label={costComp.predictive?.label}
                        cost={costComp.predictive?.cost}
                        hours={costComp.predictive?.downtime_hours}
                        desc={costComp.predictive?.description}
                        color="emerald"
                        highlight
                      />
                    </div>

                    {/* Savings summary */}
                    <div className="flex items-center justify-between bg-emerald-950/50 rounded-xl px-4 py-3 border border-emerald-600/30">
                      <div className="flex items-center gap-2">
                        <TrendingDown size={16} className="text-emerald-400" />
                        <span className="text-xs text-emerald-300 font-bold">Savings with Gantry 3.0:</span>
                      </div>
                      <div className="flex gap-5 text-sm">
                        <span className="text-emerald-400 font-bold">
                          ${costComp.savings_vs_reactive?.toLocaleString()} vs Reactive
                          <span className="text-emerald-500/80 text-xs ml-1">({costComp.savings_pct_reactive}%)</span>
                        </span>
                        <span className="text-emerald-400 font-bold">
                          ${costComp.savings_vs_preventive?.toLocaleString()} vs Preventive
                          <span className="text-emerald-500/80 text-xs ml-1">({costComp.savings_pct_preventive}%)</span>
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Downtime elapsed in solution state */}
                <div className="rounded-xl border border-amber-600/40 bg-amber-950/20 px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock size={16} className="text-amber-400" />
                    <span className="text-sm text-amber-300 font-bold">System Downtime:</span>
                  </div>
                  <span className="text-xl font-mono font-bold text-amber-400">{fmtTime(downtime)}</span>
                </div>
              </motion.div>
            )}

            {/* Cycle / status bar with downtime counter */}
            {!decision && (
              <div className="px-8 pb-5 space-y-3">
                <div className="bg-red-950/40 border border-red-800/40 rounded-xl px-5 py-3.5 flex items-center gap-3">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
                  </span>
                  <span className="text-sm text-red-300 tracking-wide">
                    {solving
                      ? "Agents analyzing failure — solution incoming…"
                      : <>Live Cycle <span className="font-bold">{cycle}</span> — immediate attention required</>
                    }
                  </span>
                </div>
                {/* Downtime counter */}
                <div className="bg-red-950/30 border border-red-800/30 rounded-xl px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock size={16} className="text-red-400" />
                    <span className="text-sm text-red-300 font-semibold uppercase tracking-wider">System Halted — Downtime</span>
                  </div>
                  <span className="text-2xl font-mono font-bold text-red-400 animate-pulse">{fmtTime(downtime)}</span>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="px-8 pb-8 flex items-center gap-4">
              {decision ? (
                <>
                  <button
                    onClick={handleAccept}
                    className="flex-1 py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white text-sm font-bold tracking-widest uppercase transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                  >
                    Accept &amp; Resume System
                  </button>
                  <button
                    onClick={handleAccept}
                    className="px-6 py-3.5 rounded-xl border border-emerald-700/50 text-emerald-300 text-sm font-bold tracking-widest uppercase hover:bg-emerald-900/30 transition-all"
                  >
                    Dismiss
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => { onOrchestrate?.(); onDismiss(); }}
                    className="flex-1 py-3.5 rounded-xl bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white text-sm font-bold tracking-widest uppercase transition-all shadow-[0_0_20px_rgba(239,68,68,0.3)]"
                    disabled={solving}
                  >
                    {solving ? "Agents Working…" : "Run Orchestration"}
                  </button>
                  <button
                    onClick={onDismiss}
                    className="px-6 py-3.5 rounded-xl border border-red-700/50 text-red-300 text-sm font-bold tracking-widest uppercase hover:bg-red-900/30 transition-all"
                  >
                    Acknowledge
                  </button>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ── Step icon helper ──────────────────────────────────────────────────── */
const STEP_ICON_MAP = {
  "ES|QL":       <Radio size={11} className="text-blue-400" />,
  "Watchman":    <AlertTriangle size={11} className="text-amber-400" />,
  "Foreman":     <User size={11} className="text-emerald-400" />,
  "DRL Policy":  <Brain size={11} className="text-purple-400" />,
  "Shadow Model":<Layers size={11} className="text-orange-400" />,
  "Gantry AI":   <ShieldCheck size={11} className="text-emerald-400" />,
};
function StepIcon({ agent }) {
  return STEP_ICON_MAP[agent] || <Radio size={11} className="text-slate-400" />;
}

/* ── Small telemetry stat card ─────────────────────────────────────────── */
function TelemetryCard({ label, value, sub, icon, critical, accent = "red" }) {
  const borderCritical = accent === "emerald" ? "bg-emerald-900/40 border-emerald-600/60" : "bg-red-900/40 border-red-600/60";
  const borderDefault  = accent === "emerald" ? "bg-midnight/60 border-emerald-800/30" : "bg-midnight/60 border-red-800/30";
  const labelColor     = accent === "emerald" ? "text-emerald-400/80" : "text-red-400/80";
  return (
    <div className={`rounded-xl border px-4 py-4 text-center ${
      critical ? borderCritical : borderDefault
    }`}>
      <div className="flex items-center justify-center gap-1.5 mb-2">
        {icon}
        <span className={`text-xs uppercase tracking-widest font-semibold ${labelColor}`}>{label}</span>
      </div>
      <p className={`text-2xl font-bold leading-none ${critical ? `${accent === "emerald" ? "text-emerald-300" : "text-red-300"} animate-pulse` : "text-slate-200"}`}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

/* ── Cost comparison card ─────────────────────────────────────────────── */
function CostCard({ label, cost, hours, desc, color = "red", highlight = false }) {
  const colorMap = {
    red:     { bg: "bg-red-950/40",     border: "border-red-600/50",     text: "text-red-300",     sub: "text-red-400/70" },
    amber:   { bg: "bg-amber-950/40",   border: "border-amber-600/50",   text: "text-amber-300",   sub: "text-amber-400/70" },
    emerald: { bg: "bg-emerald-950/40", border: "border-emerald-600/50", text: "text-emerald-300", sub: "text-emerald-400/70" },
  };
  const c = colorMap[color] || colorMap.red;
  return (
    <div className={`rounded-xl border p-4 text-center ${c.bg} ${c.border} ${
      highlight ? "ring-1 ring-emerald-400/40 shadow-[0_0_15px_rgba(16,185,129,0.15)]" : ""
    }`}>
      <p className={`text-[11px] font-bold uppercase tracking-widest mb-2 ${c.sub}`}>
        {label?.split("(")[0]?.trim()}
      </p>
      <p className={`text-2xl font-bold leading-none ${c.text}`}>
        ${cost?.toLocaleString()}
      </p>
      <p className="text-xs text-slate-500 mt-1.5">per event</p>
      <div className="mt-2 border-t border-white/5 pt-2">
        <p className={`text-sm font-bold ${c.text}`}>{hours}h</p>
        <p className="text-xs text-slate-500">downtime</p>
      </div>
      {highlight && (
        <div className="mt-2">
          <span className="text-[10px] font-bold text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
            ✓ RECOMMENDED
          </span>
        </div>
      )}
    </div>
  );
}
