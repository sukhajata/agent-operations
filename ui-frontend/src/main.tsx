import React, { useState, useEffect, useRef } from "react";
import ReactDOM from "react-dom/client";

interface Commitment {
  commitment_id: string;
  domain: string;
  priority_signal: number;
  created_at: string;
  plan_preview: string;
  understanding: string;
}

interface Status {
  pending_approval: number | string;
  executing: number | string;
  completed: number | string;
}

interface Mandate {
  mandate_id: string;
  name: string;
  domain: string;
  agent_type: string;
  focus_id: string | null;
  polling_interval_minutes: number;
  signal_threshold: number;
  active: boolean;
}

function App() {
  const [tab, setTab] = useState<"approvals" | "mandates">("approvals");
  const [pending, setPending] = useState<Commitment[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [showEvents, setShowEvents] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [mandates, setMandates] = useState<Mandate[]>([]);
  const [editingMandate, setEditingMandate] = useState<Mandate | null>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  const refresh = async () => {
    const [pRes, sRes] = await Promise.all([
      fetch("/api/pending").then((r) => r.json()),
      fetch("/api/status").then((r) => r.json()),
    ]);
    setPending(pRes.pending);
    setStatus(sRes);
  };

  const refreshMandates = async () => {
    const res = await fetch("/api/mandates").then((r) => r.json());
    setMandates(res.mandates || []);
  };

  useEffect(() => {
    refresh();
    refreshMandates();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { chatRef.current?.scrollTo(0, chatRef.current.scrollHeight); }, [messages]);

  const handleAction = async (commitmentId: string, action: string, reason?: string) => {
    const body: Record<string, string> = { commitment_id: commitmentId };
    if (reason) body.reason = reason;
    await fetch("/api/actions/execute", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, parameters: body }) });
    refresh();
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const text = chatInput;
    setChatInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    try {
      const allMessages = [...messages.filter((m) => m.role !== "system"), { role: "user", content: text }];
      const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: allMessages }) });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.content || "(no response)" }]);
      refresh();
    } catch (e) {
      setMessages((prev) => [...prev, { role: "system", content: `Error: ${e}` }]);
    }
    setLoading(false);
  };

  const saveMandate = async () => {
    if (!editingMandate) return;
    const m = editingMandate;
    const body = { ...m, polling_interval_minutes: Number(m.polling_interval_minutes), signal_threshold: Number(m.signal_threshold) };
    const url = m.mandate_id ? `/api/mandates/${m.mandate_id}` : "/api/mandates";
    const method = m.mandate_id ? "PUT" : "POST";
    await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setEditingMandate(null);
    refreshMandates();
  };

  const deleteMandate = async (id: string) => {
    await fetch(`/api/mandates/${id}`, { method: "DELETE" });
    refreshMandates();
  };

  const newMandate = () => setEditingMandate({
    mandate_id: "", name: "", domain: "", agent_type: "free", focus_id: null,
    polling_interval_minutes: 30, signal_threshold: 0.6, active: true,
  });

  const btn = (bg: string, text: string, onClick: () => void) => (
    <button onClick={onClick} style={{ padding: "0.4rem 1rem", background: bg, color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>{text}</button>
  );

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "system-ui" }}>
      <div style={{ width: "45%", borderRight: "1px solid #e0e0e0", overflow: "auto", padding: "1rem" }}>
        <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
          <button onClick={() => setTab("approvals")} style={{ fontWeight: tab === "approvals" ? "bold" : "normal", border: "none", background: "none", cursor: "pointer", fontSize: "1rem" }}>Approvals</button>
          <button onClick={() => { setTab("mandates"); refreshMandates(); }} style={{ fontWeight: tab === "mandates" ? "bold" : "normal", border: "none", background: "none", cursor: "pointer", fontSize: "1rem" }}>Mandates</button>
          {status && <span style={{ fontSize: "0.8rem", color: "#888", marginLeft: "auto" }}>{String(status.pending_approval)} pending | {String(status.executing)} executing | {String(status.completed)} completed</span>}
        </div>

        {tab === "approvals" && (
          <>
            {pending.length === 0 && <p style={{ color: "#888" }}>No pending commitments.</p>}
            {pending.map((c) => (
              <div key={c.commitment_id} style={{ border: "1px solid #e0e0e0", borderRadius: "8px", padding: "1rem", marginBottom: "1rem" }}>
                <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>{c.commitment_id} <span style={{ color: "#666" }}>| {c.domain}</span></div>
                <div style={{ fontSize: "0.85rem", color: "#555", marginBottom: "0.5rem" }}>{c.plan_preview?.slice(0, 400) || "(no plan)"}</div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {btn("#22c55e", "Approve", () => handleAction(c.commitment_id, "approveCommitment"))}
                  {btn("#ef4444", "Reject", () => handleAction(c.commitment_id, "rejectCommitment", "rejected via UI"))}
                  {btn("#f59e0b", "Defer", () => handleAction(c.commitment_id, "deferCommitment", "deferred via UI"))}
                </div>
              </div>
            ))}
            <div style={{ marginTop: "1rem", borderTop: "1px solid #e0e0e0", paddingTop: "1rem" }}>
              <button onClick={() => { setShowEvents(!showEvents); if (!showEvents) fetch("/api/events/recent?limit=30").then(r => r.json()).then(d => setEvents(d.events || [])); }} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1rem", color: "#3b82f6" }}>{showEvents ? "▼ Hide" : "▶ Show"} Recent Activity</button>
              {showEvents && (
                <div style={{ marginTop: "0.5rem", maxHeight: "300px", overflow: "auto" }}>
                  {events.map((e: any, i: number) => (
                    <div key={i} style={{ padding: "0.4rem", borderBottom: "1px solid #f0f0f0", fontSize: "0.8rem", background: e.type === "finding" ? (e.verdict === "confirmed" ? "#f0fdf4" : "#fef2f2") : "transparent" }}>
                      <span style={{ color: "#999", marginRight: "0.5rem" }}>{e.ts?.slice(11, 19)}</span>
                      <span style={{ fontWeight: 600, color: e.type === "finding" ? "#9333ea" : "#2563eb" }}>{e.type === "finding" ? `[${e.verdict}]` : "[signal]"}</span>
                      <span style={{ color: "#666" }}> {e.domain}</span>
                      <span style={{ color: "#999", marginLeft: "0.5rem" }}>conf: {e.confidence?.toFixed(2)}</span>
                      <div style={{ color: "#444" }}>{e.claim}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {tab === "mandates" && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <span>{mandates.length} mandate(s)</span>
              {btn("#3b82f6", "+ New Mandate", newMandate)}
            </div>
            {editingMandate && (
              <div style={{ border: "1px solid #3b82f6", borderRadius: "8px", padding: "1rem", marginBottom: "1rem", background: "#f8fafc" }}>
                <h3 style={{ marginTop: 0 }}>{editingMandate.mandate_id ? "Edit Mandate" : "New Mandate"}</h3>
                {(["name", "domain"] as const).map((f) => (
                  <div key={f} style={{ marginBottom: "0.5rem" }}>
                    <label style={{ fontSize: "0.8rem", display: "block" }}>{f}</label>
                    <input value={editingMandate[f]} onChange={(e) => setEditingMandate({ ...editingMandate, [f]: e.target.value })} style={{ width: "100%", padding: "0.3rem" }} />
                  </div>
                ))}
                <div style={{ marginBottom: "0.5rem" }}>
                  <label style={{ fontSize: "0.8rem", display: "block" }}>agent_type</label>
                  <select value={editingMandate.agent_type} onChange={(e) => setEditingMandate({ ...editingMandate, agent_type: e.target.value })} style={{ width: "100%", padding: "0.3rem" }}>
                    <option value="free">free</option>
                    <option value="focus">focus</option>
                  </select>
                </div>
                {editingMandate.agent_type === "focus" && (
                  <div style={{ marginBottom: "0.5rem" }}>
                    <label style={{ fontSize: "0.8rem", display: "block" }}>focus_id</label>
                    <input value={editingMandate.focus_id || ""} onChange={(e) => setEditingMandate({ ...editingMandate, focus_id: e.target.value })} style={{ width: "100%", padding: "0.3rem" }} />
                  </div>
                )}
                {(["polling_interval_minutes", "signal_threshold"] as const).map((f) => (
                  <div key={f} style={{ marginBottom: "0.5rem" }}>
                    <label style={{ fontSize: "0.8rem", display: "block" }}>{f}</label>
                    <input type="number" step="0.1" value={editingMandate[f]} onChange={(e) => setEditingMandate({ ...editingMandate, [f]: e.target.value })} style={{ width: "100%", padding: "0.3rem" }} />
                  </div>
                ))}
                <div style={{ marginBottom: "0.5rem" }}>
                  <label style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <input type="checkbox" checked={editingMandate.active} onChange={(e) => setEditingMandate({ ...editingMandate, active: e.target.checked })} />
                    active
                  </label>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {btn("#22c55e", "Save", saveMandate)}
                  {btn("#6b7280", "Cancel", () => setEditingMandate(null))}
                </div>
              </div>
            )}
            {mandates.map((m) => (
              <div key={m.mandate_id} style={{ border: "1px solid #e0e0e0", borderRadius: "8px", padding: "0.75rem", marginBottom: "0.5rem", opacity: m.active ? 1 : 0.5 }}>
                <div style={{ fontWeight: "bold" }}>{m.name} <span style={{ color: "#666", fontWeight: "normal" }}>| {m.domain}</span></div>
                <div style={{ fontSize: "0.8rem", color: "#666" }}>{m.agent_type} · {m.polling_interval_minutes}min · threshold {m.signal_threshold}</div>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                  {btn("#3b82f6", "Edit", () => setEditingMandate(m))}
                  {btn("#ef4444", "Delete", () => deleteMandate(m.mandate_id))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ width: "55%", display: "flex", flexDirection: "column", padding: "1rem" }}>
        <h2>Chat</h2>
        <div ref={chatRef} style={{ flex: 1, overflow: "auto", border: "1px solid #e0e0e0", borderRadius: "8px", padding: "1rem", marginBottom: "1rem", background: "#fafafa" }}>
          {messages.length === 0 && <p style={{ color: "#888" }}>Ask anything. Try: "what's the status?", "show pending", "approve com-xxx"</p>}
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: "0.5rem", padding: "0.5rem", borderRadius: "6px", background: m.role === "user" ? "#e0f2fe" : m.role === "system" ? "#fef3c7" : "#f0fdf4", whiteSpace: "pre-wrap" }}>
              <strong style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#666" }}>{m.role}</strong>
              <div style={{ marginTop: "0.25rem" }}>{m.content}</div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleChat()} placeholder="Ask about commitments, approve plans..." style={{ flex: 1, padding: "0.6rem", borderRadius: "4px", border: "1px solid #ccc" }} />
          <button onClick={handleChat} disabled={loading} style={{ padding: "0.6rem 1.5rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>{loading ? "..." : "Send"}</button>
        </div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
