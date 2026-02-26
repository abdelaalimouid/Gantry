import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu, ShieldCheck, Wifi, WifiOff } from "lucide-react";

import Header          from "./components/Header";
import TelemetryPanel  from "./components/TelemetryPanel";
import DigitalTwin     from "./components/DigitalTwin";
import ReasoningLog    from "./components/ReasoningLog";
import JudgingBanner   from "./components/JudgingBanner";
import ChatPanel       from "./components/ChatPanel";
import CriticalOverlay from "./components/CriticalOverlay";
import useWebSocket    from "./hooks/useWebSocket";

const API_BASE = "/api";

export default function App() {
  const [data, setData]           = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [judgingMode, setJudging]  = useState(false);
  const [unitId, setUnitId]       = useState("ENGINE-001");

  // ── Live WebSocket telemetry ──────────────────────────────────────
  const {
    lastMessage: liveTel,
    lastAlert,
    connected: wsConnected,
    criticalEvent,
    dismissCritical,
    streamingLogs,
    resetStreamingLogs,
    agentSolution,
    clearSolution,
  } = useWebSocket(unitId);

  // ── Orchestrate ───────────────────────────────────────────────────
  const runOrchestration = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/orchestrate/${encodeURIComponent(unitId)}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [unitId]);

  // Called when user sends "Override" in chat
  const handleOverride = useCallback(() => {
    // Re-run orchestration automatically so the override takes effect
    runOrchestration();
  }, [runOrchestration]);

  // When dismissing the overlay, clear all failure state so dashboard returns to live healthy mode
  const handleDismissOverlay = useCallback(() => {
    // Reset data so the UI falls back to live WS values (healthy simulation)
    setData(null);
    dismissCritical();
    clearSolution();
    resetStreamingLogs();
  }, [dismissCritical, clearSolution, resetStreamingLogs]);

  // Prefer live WS status; fall back to orchestration snapshot; default IDLE (green)
  // After a resume, liveTel is null until the next healthy tick arrives
  const status = liveTel?.unit_status ?? data?.status ?? "IDLE";

  return (
    <div className="min-h-screen bg-midnight flex flex-col">
      {/* ── Critical State Overlay ────────────────────────────── */}
      <CriticalOverlay
        visible={!!criticalEvent}
        telemetry={criticalEvent ?? liveTel}
        agentSolution={agentSolution}
        streamingLogs={streamingLogs}
        onDismiss={handleDismissOverlay}
        onOrchestrate={runOrchestration}
      />

      {/* ── Header ────────────────────────────────────────────── */}
      <Header
        unitId={unitId}
        setUnitId={setUnitId}
        onRun={runOrchestration}
        loading={loading}
        judgingMode={judgingMode}
        setJudging={setJudging}
      />

      {/* ── Error bar ─────────────────────────────────────────── */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-red-900/60 border-b border-red-700 text-red-200 text-xs px-6 py-2 font-mono"
          >
            Error: {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Judging banner ────────────────────────────────────── */}
      <AnimatePresence>
        {judgingMode && data && (
          <JudgingBanner costSaved={data.cost_impact?.cost_saved ?? 0} shadow={data.shadow_model} />
        )}
      </AnimatePresence>

      {/* ── Three-Column Grid ─────────────────────────────────── */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 lg:p-6 overflow-auto">
        {/* LEFT — Physical Telemetry */}
        <TelemetryPanel data={data} live={liveTel} />

        {/* CENTER — Digital Twin Canvas + Chat */}
        <div className="flex flex-col gap-4">
          <DigitalTwin status={status} data={data} loading={loading} live={liveTel} failureActive={!!criticalEvent} />
          <ChatPanel unitId={unitId} onOverride={handleOverride} lastAlert={lastAlert} />
        </div>

        {/* RIGHT — Neural Reasoning Log */}
        <ReasoningLog data={data} streamingLogs={streamingLogs} />
      </main>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="border-t border-border px-6 py-3 flex items-center justify-between text-[10px] text-slate-500 font-mono">
        <span className="flex items-center gap-1.5">
          <Cpu size={12} /> Gantry 3.0 Digital Twin — PPO Policy v1
        </span>
        <span className="flex items-center gap-1.5">
          {wsConnected
            ? <><Wifi size={12} className="text-emerald-400" /> WebSocket Live</>
            : <><WifiOff size={12} className="text-slate-600" /> WS Disconnected</>
          }
        </span>
        <span className="flex items-center gap-1.5">
          <ShieldCheck size={12} /> MCP Protocol 2024-11-05
        </span>
      </footer>
    </div>
  );
}

