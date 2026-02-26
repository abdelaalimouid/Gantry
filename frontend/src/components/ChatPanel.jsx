import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Send, ShieldAlert, Bot, User, ShieldOff, AlertTriangle } from "lucide-react";

const API_BASE = "/api";

export default function ChatPanel({ unitId, onOverride, lastAlert }) {
  const [messages, setMessages] = useState([
    { role: "system", text: "GANTRY supervisor online. Ask me anything about the engine — status, costs, crew, or type \"Override\" to take manual control." },
  ]);
  const [input, setInput]     = useState("");
  const [sending, setSending] = useState(false);
  const [overrideFlash, setOverrideFlash] = useState(false);
  const [alertFlash, setAlertFlash] = useState(false);
  const bottomRef = useRef(null);
  const lastAlertRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Handle system-initiated alerts from WebSocket ────────────
  useEffect(() => {
    if (lastAlert && lastAlert !== lastAlertRef.current) {
      lastAlertRef.current = lastAlert;
      setMessages((m) => [
        ...m,
        {
          role: "alert",
          text: lastAlert.message || `⚠️ Critical alert for ${lastAlert.unit_id}`,
        },
      ]);
      setAlertFlash(true);
      setTimeout(() => setAlertFlash(false), 3000);
    }
  }, [lastAlert]);

  const send = async () => {
    const msg = input.trim();
    if (!msg || sending) return;

    setMessages((m) => [...m, { role: "user", text: msg }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, unit_id: unitId }),
      });
      const data = await res.json();

      // Override detected — flash + system message
      if (data.override_active) {
        setMessages((m) => [
          ...m,
          { role: "override", text: data.reply || "⚠️ HUMAN OVERRIDE ACTIVATED" },
        ]);
        setOverrideFlash(true);
        setTimeout(() => setOverrideFlash(false), 2000);
        onOverride?.();
      } else {
        setMessages((m) => [...m, { role: "agent", text: data.reply || "No response." }]);
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "agent", text: `Error: ${e.message}` }]);
    } finally {
      setSending(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
      className={`bg-panel border rounded-xl flex flex-col overflow-hidden transition-all duration-500 ${
        alertFlash
          ? "border-red-500 shadow-[0_0_30px_rgba(239,68,68,0.35)]"
          : overrideFlash
          ? "border-amber-500 shadow-[0_0_30px_rgba(245,158,11,0.3)]"
          : "border-border"
      }`}
      style={{ maxHeight: 520 }}
    >
      {/* Header */}
      <div className={`flex items-center gap-2 px-4 py-2.5 border-b transition-colors duration-500 ${
        alertFlash ? "border-red-500/50 bg-red-900/20" :
        overrideFlash ? "border-amber-500/50 bg-amber-900/20" : "border-border"
      }`}>
        <MessageSquare size={16} className="text-accent" />
        <h3 className="text-[12px] font-bold tracking-widest text-slate-400 uppercase">
          Agent Chat
        </h3>
        <span className="ml-auto text-[11px] text-slate-500 tracking-wide flex items-center gap-1">
          {alertFlash && <AlertTriangle size={11} className="text-red-400 animate-pulse" />}
          {overrideFlash && <ShieldOff size={11} className="text-amber-400 animate-pulse" />}
          Human-in-the-Loop
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-2 items-start ${m.role === "user" ? "justify-end" : ""}`}
            >
              {m.role !== "user" && (
                <div className={`w-7 h-7 rounded-full border flex items-center justify-center flex-shrink-0 mt-0.5 ${
                  m.role === "override"
                    ? "bg-amber-900/40 border-amber-600"
                    : m.role === "alert"
                    ? "bg-red-900/40 border-red-600"
                    : "bg-midnight border-border"
                }`}>
                  {m.role === "agent"
                    ? <Bot size={14} className="text-cyan-400" />
                    : m.role === "override"
                    ? <ShieldOff size={14} className="text-amber-400" />
                    : m.role === "alert"
                    ? <AlertTriangle size={14} className="text-red-400 animate-pulse" />
                    : <ShieldAlert size={14} className="text-amber-400" />
                  }
                </div>
              )}
              <div
                className={`rounded-lg px-4 py-2.5 text-[12px] leading-relaxed max-w-[85%] ${
                  m.role === "user"
                    ? "bg-cyan-800/30 border border-cyan-700/40 text-cyan-100"
                    : m.role === "override"
                    ? "bg-amber-900/30 border border-amber-600/50 text-amber-200 font-semibold"
                    : m.role === "alert"
                    ? "bg-red-900/40 border-2 border-red-500/70 text-red-200 font-semibold shadow-[0_0_12px_rgba(239,68,68,0.25)]"
                    : m.role === "agent"
                    ? "bg-midnight/60 border border-border text-slate-300"
                    : "bg-amber-900/20 border border-amber-700/30 text-amber-200 italic"
                }`}
              >
                {m.text}
              </div>
              {m.role === "user" && (
                <div className="w-7 h-7 rounded-full bg-cyan-700/30 border border-cyan-600/40 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <User size={14} className="text-cyan-300" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border px-3 py-3 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder='Ask about engine state or type "Override"…'
          className="flex-1 bg-midnight border border-border rounded px-3 py-2 text-[12px] text-slate-300 placeholder-slate-600 focus:border-accent focus:outline-none transition-colors"
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          className="p-2.5 rounded bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-40 transition-all"
        >
          <Send size={14} className="text-white" />
        </button>
      </div>
    </motion.section>
  );
}
