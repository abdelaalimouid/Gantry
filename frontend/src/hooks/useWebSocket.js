import { useEffect, useRef, useState, useCallback } from "react";

/**
 * useWebSocket – connects to ws://host/ws/telemetry/{unitId} and
 * pushes incoming JSON messages to the caller via `lastMessage`.
 * Also captures system alerts (type: "alert") separately, and
 * detects `isError: true` and `unit_status: "CRITICAL"` transitions.
 *
 * Streaming MCP steps (type: "mcp_step") are accumulated in `streamingLogs`.
 *
 * Auto-reconnects with exponential backoff.
 */
export default function useWebSocket(unitId) {
  const [lastMessage, setLastMessage] = useState(null);
  const [lastAlert, setLastAlert] = useState(null);
  const [connected, setConnected] = useState(false);
  const [criticalEvent, setCriticalEvent] = useState(null);
  const [streamingLogs, setStreamingLogs] = useState([]);
  const [agentSolution, setAgentSolution] = useState(null);
  const wsRef = useRef(null);
  const timer = useRef(null);
  const tries = useRef(0);

  const dismissCritical = useCallback(() => setCriticalEvent(null), []);
  const resetStreamingLogs = useCallback(() => setStreamingLogs([]), []);
  const clearSolution = useCallback(() => setAgentSolution(null), []);

  const connect = useCallback(() => {
    if (!unitId) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/telemetry/${encodeURIComponent(unitId)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      tries.current = 0;
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);

        // ── Streaming MCP step (Watchman / Foreman / etc.) ───────────
        if (data.type === "mcp_step") {
          setStreamingLogs((prev) => {
            if (prev.some((s) => s.step === data.step)) return prev;
            return [...prev, data];
          });
          return;
        }

        // ── Agent solution (final orchestration result) ─────────────
        if (data.type === "solution") {
          setAgentSolution(data);
          return;
        }

        // ── System-initiated alert ──────────────────────────────────
        if (data.type === "alert") {
          setLastAlert(data);
          if (data.isError || data.severity === "critical") {
            setCriticalEvent(data);
          }
          return;
        }

        // ── System resumed after failure resolved ───────────────────
        if (data.type === "system_resumed") {          // Clear frozen failure snapshot so dashboard snaps back to healthy
          setLastMessage(null);          setCriticalEvent(null);
          setStreamingLogs([]);
          setAgentSolution(null);
          return;
        }

        // ── Normal telemetry tick ───────────────────────────────────
        setLastMessage(data);

        // NOTE: Do NOT trigger the critical overlay from regular telemetry.
        // The overlay is reserved for explicit alert broadcasts (e.g. trigger_failure.py).
      } catch {
        /* ignore non-JSON */
      }
    };

    ws.onclose = () => {
      setConnected(false);
      const delay = Math.min(2000 * 2 ** tries.current, 30000);
      tries.current += 1;
      timer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [unitId]);

  useEffect(() => {
    setStreamingLogs([]);
    setAgentSolution(null);
    connect();
    return () => {
      clearTimeout(timer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return {
    lastMessage,
    lastAlert,
    connected,
    criticalEvent,
    dismissCritical,
    streamingLogs,
    resetStreamingLogs,
    agentSolution,
    clearSolution,
  };
}
