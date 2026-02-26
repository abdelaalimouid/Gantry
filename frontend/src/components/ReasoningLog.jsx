import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck, AlertTriangle, User, Brain, Radio,
  Layers, ShieldOff, CheckCircle2, XCircle, DollarSign,
} from "lucide-react";

const STEP_ICONS = {
  "ES|QL":          <Radio size={14} className="text-blue-400" />,
  "Watchman":       <AlertTriangle size={14} className="text-amber-400" />,
  "Foreman":        <User size={14} className="text-emerald-400" />,
  "DRL Policy":     <Brain size={14} className="text-purple-400" />,
  "Shadow Model":   <Layers size={14} className="text-orange-400" />,
  "Human Override": <ShieldOff size={14} className="text-red-400" />,
};

/* ── Typewriter Text ──────────────────────────────────────── */
function TypewriterText({ text, speed = 18, onComplete }) {
  const [displayed, setDisplayed] = useState("");
  const idx = useRef(0);
  const timerRef = useRef(null);

  useEffect(() => {
    // Reset when text changes
    setDisplayed("");
    idx.current = 0;

    if (!text) return;

    timerRef.current = setInterval(() => {
      idx.current += 1;
      setDisplayed(text.slice(0, idx.current));
      if (idx.current >= text.length) {
        clearInterval(timerRef.current);
        onComplete?.();
      }
    }, speed);

    return () => clearInterval(timerRef.current);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {displayed.length < (text?.length ?? 0) && (
        <span className="inline-block w-[5px] h-[12px] bg-slate-400 ml-0.5 animate-pulse rounded-sm" />
      )}
    </span>
  );
}

/* ── Shadow Model Comparison Card ─────────────────────────── */
function ShadowCard({ shadow }) {
  if (!shadow || !shadow.conflict) return null;

  const pill = (decision) =>
    decision === "APPROVE"
      ? "bg-emerald-900/40 border-emerald-600/50 text-emerald-300"
      : "bg-red-900/40 border-red-600/50 text-red-300";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.9, type: "spring", stiffness: 200 }}
      className="rounded-lg border border-orange-600/40 bg-gradient-to-br from-orange-950/30 to-midnight/60 p-4 space-y-3"
    >
      <p className="text-[10px] font-bold text-orange-400 uppercase tracking-widest flex items-center gap-1.5">
        <Layers size={12} /> Shadow Model — Conflict Detected
      </p>

      {/* Side-by-side comparison */}
      <div className="grid grid-cols-2 gap-2">
        {/* Simple Rule */}
        <div className="rounded border border-border bg-midnight/50 p-3 space-y-1.5">
          <p className="text-[10px] text-slate-500 font-semibold tracking-wide uppercase">Standard Rule</p>
          <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded border ${pill(shadow.simple_rule?.decision)}`}>
            {shadow.simple_rule?.decision === "APPROVE"
              ? <CheckCircle2 size={11} />
              : <XCircle size={11} />}
            {shadow.simple_rule?.decision}
          </span>
          <p className="text-[10px] text-slate-400 leading-snug">{shadow.simple_rule?.reason}</p>
        </div>

        {/* DRL Policy */}
        <div className="rounded border border-purple-700/40 bg-purple-950/20 p-3 space-y-1.5">
          <p className="text-[10px] text-purple-400 font-semibold tracking-wide uppercase">DRL Policy</p>
          <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded border ${pill(shadow.drl_policy?.decision)}`}>
            {shadow.drl_policy?.decision === "APPROVE"
              ? <CheckCircle2 size={11} />
              : <XCircle size={11} />}
            {shadow.drl_policy?.decision}
          </span>
          <p className="text-[10px] text-slate-400 leading-snug">{shadow.drl_policy?.reason}</p>
        </div>
      </div>

      {/* Enterprise Verdict */}
      <div className="flex items-center justify-between rounded bg-midnight/50 border border-amber-700/30 px-3 py-2">
        <p className="text-[11px] font-bold text-amber-300">{shadow.enterprise_verdict}</p>
        {shadow.cost_saved && (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-400">
            <DollarSign size={12} />{shadow.cost_saved} saved
          </span>
        )}
      </div>
    </motion.div>
  );
}

/* ── Main Component ───────────────────────────────────────── */
export default function ReasoningLog({ data, streamingLogs }) {
  const logs    = streamingLogs?.length ? streamingLogs : (data?.mcp_logs ?? []);
  const reason  = data?.drl_decision?.reason ?? null;
  const shadow  = data?.shadow_model ?? null;

  // Track which steps have finished their typewriter animation
  const [finishedSteps, setFinishedSteps] = useState(new Set());
  const prevLogsLen = useRef(0);

  // Reset finished steps when orchestration data changes
  useEffect(() => {
    if (logs.length < prevLogsLen.current) {
      setFinishedSteps(new Set());
    }
    prevLogsLen.current = logs.length;
  }, [logs.length]);

  const markFinished = (step) => {
    setFinishedSteps((prev) => new Set([...prev, step]));
  };

  return (
    <motion.section
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-panel border border-border rounded-xl p-5 flex flex-col gap-5"
    >
      <h2 className="text-xs font-bold tracking-widest text-slate-400 uppercase flex items-center gap-2">
        <ShieldCheck size={14} className="text-accent" />
        Neural Reasoning Log
      </h2>

      {/* Timeline */}
      <div className="flex-1 flex flex-col gap-0 relative">
        {/* Vertical line */}
        <div className="absolute top-2 bottom-2 left-[18px] w-px bg-border" />

        {logs.length === 0 && (
          <p className="text-xs text-slate-500 italic pl-10 py-8">
            Run orchestration to generate the reasoning timeline.
          </p>
        )}

        <AnimatePresence initial={false}>
          {logs.map((log, i) => (
            <motion.div
              key={log.step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.25 + i * 0.15 }}
              className="relative flex items-start gap-3 py-3"
            >
              {/* Dot */}
              <div className={`relative z-10 w-9 h-9 rounded-full border flex items-center justify-center flex-shrink-0 ${
                log.agent === "Shadow Model"
                  ? "bg-orange-950/50 border-orange-600/60"
                  : log.agent === "Human Override"
                  ? "bg-red-950/50 border-red-600/60"
                  : "bg-midnight border-border"
              }`}>
                {STEP_ICONS[log.agent] ?? <Radio size={14} className="text-slate-400" />}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className={`text-[11px] font-bold tracking-wide ${
                  log.agent === "Shadow Model" ? "text-orange-300" :
                  log.agent === "Human Override" ? "text-red-300" :
                  "text-slate-300"
                }`}>
                  {log.agent}
                </p>
                <p className="text-[11px] text-slate-400 leading-relaxed break-words">
                  {finishedSteps.has(log.step) ? (
                    log.event
                  ) : (
                    <TypewriterText
                      text={log.event}
                      speed={14}
                      onComplete={() => markFinished(log.step)}
                    />
                  )}
                </p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Shadow Model Comparison Card */}
      <ShadowCard shadow={shadow} />

      {/* "Why Card" */}
      {reason && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="bg-midnight/60 rounded-lg border border-amber-700/40 p-4"
        >
          <p className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-1 flex items-center gap-1.5">
            <Brain size={12} /> Why This Decision?
          </p>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            {reason}
          </p>
        </motion.div>
      )}
    </motion.section>
  );
}
