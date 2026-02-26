import { motion } from "framer-motion";
import { DollarSign, AlertTriangle, ShieldCheck, Layers } from "lucide-react";

export default function JudgingBanner({ costSaved, shadow }) {
  const hasVeto = costSaved > 0;
  const conflict = shadow?.conflict;

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="overflow-hidden"
    >
      {/* Cost savings bar */}
      <div
        className={`flex items-center justify-center gap-3 px-6 py-3 text-sm font-bold tracking-wider border-b ${
          hasVeto
            ? "bg-emerald-900/40 border-emerald-700 text-emerald-300"
            : "bg-slate-800/40 border-border text-slate-400"
        }`}
      >
        <DollarSign size={18} className={hasVeto ? "text-emerald-400" : "text-slate-500"} />
        {hasVeto
          ? `$${costSaved.toFixed(0)} Saved — DRL Veto prevented unnecessary express shipping`
          : "No cost savings this cycle — express shipping was approved"}
      </div>

      {/* Shadow model conflict bar (only when conflict exists) */}
      {conflict && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="flex items-center justify-center gap-4 px-6 py-2.5 bg-orange-950/30 border-b border-orange-700/40"
        >
          <Layers size={15} className="text-orange-400" />
          <span className="text-[11px] font-bold text-orange-300 tracking-wide">
            SHADOW MODEL CONFLICT
          </span>
          <span className="text-[11px] text-slate-400">
            Rule: <span className={shadow.simple_rule?.decision === "APPROVE" ? "text-emerald-400 font-semibold" : "text-red-400 font-semibold"}>{shadow.simple_rule?.decision}</span>
            {" vs "}
            DRL: <span className={shadow.drl_policy?.decision === "APPROVE" ? "text-emerald-400 font-semibold" : "text-red-400 font-semibold"}>{shadow.drl_policy?.decision}</span>
          </span>
          <span className="text-[10px] text-amber-300 font-semibold border border-amber-600/40 rounded px-2 py-0.5 bg-amber-900/20">
            Verdict: {shadow.enterprise_verdict}
          </span>
          {shadow.cost_saved > 0 && (
            <span className="text-[11px] text-emerald-400 font-bold flex items-center gap-1">
              <ShieldCheck size={12} /> ${shadow.cost_saved.toFixed(0)} protected
            </span>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}
