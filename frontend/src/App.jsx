import React, { useEffect, useState } from "react";

const SAMPLES = [
  { label: "MR: Cotton Yellowing", lang: "mr", text: "माझ्या कापूस पिकाची पाने पिवळी पडत आहेत, काय करावे?" },
  { label: "MR: Lasalgaon Onion Price", lang: "mr", text: "आज लासलगाव कांदा बाजार भाव काय आहे?" },
  { label: "HI: Wheat Yellow Rust", lang: "hi", text: "गेहूं में पीला रतुआ रोग लग गया है कौन सी दवा छिड़कें?" },
  { label: "HI: Nagpur Weather", lang: "hi", text: "नागपुर में आज मौसम और बारिश का हाल बताइए" },
  { label: "HI: PM-KISAN e-KYC", lang: "hi", text: "पीएम किसान योजना की किस्त के लिए ई-केवाईसी कैसे करें?" },
  { label: "Refusal Test (Off-topic)", lang: "en", text: "Who won yesterday's cricket match?" },
];

export default function App() {
  const [tab, setTab] = useState("simulator");
  const [role, setRole] = useState("admin");

  // Simulator state
  const [queryText, setQueryText] = useState(SAMPLES[0].text);
  const [langHint, setLangHint] = useState("mr");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [feedbackMsg, setFeedbackMsg] = useState("");

  // Admin state
  const [docs, setDocs] = useState([]);
  const [terms, setTerms] = useState([]);
  const [evalSummary, setEvalSummary] = useState(null);
  const [reviewQueue, setReviewQueue] = useState([]);

  // New term form
  const [newTerm, setNewTerm] = useState({ category: "crop", en: "", hi: "", mr: "" });

  async function runQuery(textOverride, langOverride) {
    setLoading(true);
    setFeedbackMsg("");
    try {
      const resp = await fetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textOverride ?? queryText,
          language: langOverride ?? langHint,
          phone_number: "+919876543210",
          synthesize_audio: true,
        }),
      });
      setResult(await resp.json());
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(rating) {
    if (!result?.interaction_id) return;
    await fetch("/api/v1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interaction_id: result.interaction_id, rating }),
    });
    setFeedbackMsg(rating > 0 ? "Thanks! Marked helpful." : "Flagged for expert review.");
  }

  async function loadAdminData() {
    const headers = { "X-Admin-Role": role };
    const [dRes, gRes, rRes] = await Promise.all([
      fetch("/api/v1/admin/documents", { headers }),
      fetch("/api/v1/admin/glossary", { headers }),
      fetch("/api/v1/admin/review-queue", { headers }),
    ]);
    if (dRes.ok) setDocs((await dRes.json()).documents || []);
    if (gRes.ok) setTerms((await gRes.json()).terms || []);
    if (rRes.ok) setReviewQueue((await rRes.json()).items || []);
  }

  async function setDocApproval(docId, status) {
    await fetch(`/api/v1/admin/documents/${docId}/approval?status=${status}`, {
      method: "POST",
      headers: { "X-Admin-Role": role },
    });
    loadAdminData();
  }

  async function addGlossaryTerm(e) {
    e.preventDefault();
    if (!newTerm.en || !newTerm.hi || !newTerm.mr) return;
    await fetch("/api/v1/admin/glossary", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Role": role },
      body: JSON.stringify(newTerm),
    });
    setNewTerm({ category: "crop", en: "", hi: "", mr: "" });
    loadAdminData();
  }

  async function runEvalSuite() {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/eval/run", {
        method: "POST",
        headers: { "X-Admin-Role": role },
      });
      if (res.ok) setEvalSummary(await res.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (tab !== "simulator") {
      loadAdminData();
    }
  }, [tab, role]);

  return (
    <div className="app-shell">
      <header className="header">
        <div className="brand">
          <h1>AgriAssistant</h1>
          <p>Voice-First Multilingual Agricultural Assistant (Hindi / Marathi / English)</p>
        </div>
        <div className="tabs">
          <button className={`tab-btn ${tab === "simulator" ? "active" : ""}`} onClick={() => setTab("simulator")}>
            Farmer Simulator
          </button>
          <button className={`tab-btn ${tab === "kb" ? "active" : ""}`} onClick={() => setTab("kb")}>
            Knowledge Base
          </button>
          <button className={`tab-btn ${tab === "glossary" ? "active" : ""}`} onClick={() => setTab("glossary")}>
            Glossary
          </button>
          <button className={`tab-btn ${tab === "eval" ? "active" : ""}`} onClick={() => setTab("eval")}>
            Eval & Review
          </button>
          <select className="select" value={role} onChange={(e) => setRole(e.target.value)} title="RBAC Role">
            <option value="admin">Role: Admin</option>
            <option value="reviewer">Role: Reviewer</option>
            <option value="analyst">Role: Analyst</option>
          </select>
        </div>
      </header>

      {tab === "simulator" && (
        <div>
          <div className="card">
            <div className="row" style={{ marginBottom: 10 }}>
              {SAMPLES.map((s) => (
                <button
                  key={s.label}
                  className="btn secondary"
                  onClick={() => {
                    setQueryText(s.text);
                    setLangHint(s.lang);
                    runQuery(s.text, s.lang);
                  }}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <textarea
              className="textarea"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              placeholder="Ask a question in Hindi, Marathi, English, or Hinglish..."
            />
            <div className="row" style={{ marginTop: 10, justifyContent: "space-between" }}>
              <select className="select" value={langHint} onChange={(e) => setLangHint(e.target.value)}>
                <option value="mr">Marathi (मराठी)</option>
                <option value="hi">Hindi (हिन्दी)</option>
                <option value="en">English</option>
              </select>
              <button className="btn" onClick={() => runQuery()} disabled={loading}>
                {loading ? "Processing..." : "Ask Assistant"}
              </button>
            </div>
          </div>

          {result && (
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
                <div className="row">
                  <span className={`pill ${result.decision === "refuse" ? "refuse" : result.decision === "ask_repeat" ? "repeat" : ""}`}>
                    {result.decision.toUpperCase()} ({result.reason_code})
                  </span>
                  <span className="pill">Intent: {result.intent}</span>
                  <span className="pill">Lang: {result.language}</span>
                  <span className="pill">Confidence: {(result.confidence * 100).toFixed(0)}%</span>
                  <span className="pill">{result.latency_ms} ms</span>
                </div>
              </div>
              <p style={{ fontSize: "1.1rem", lineHeight: 1.5 }}>{result.answer_text}</p>
              {result.language !== "en" && (
                <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
                  <strong>English gloss:</strong> {result.answer_english}
                </p>
              )}
              {result.sources?.length > 0 && (
                <p style={{ fontSize: "0.88rem", color: "var(--primary)" }}>
                  <strong>Sources:</strong> {result.sources.join(" | ")}
                  {result.data_as_of ? ` (Data as of ${result.data_as_of})` : ""}
                </p>
              )}
              {result.audio_url && (
                <div style={{ marginTop: 10 }}>
                  <audio controls src={result.audio_url} style={{ width: "100%" }} />
                </div>
              )}
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn secondary" onClick={() => sendFeedback(1)}>Helpful</button>
                <button className="btn secondary" onClick={() => sendFeedback(-1)}>Needs Review</button>
                {feedbackMsg && <span style={{ fontSize: "0.9rem", color: "var(--primary)" }}>{feedbackMsg}</span>}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "kb" && (
        <div className="card">
          <h3>Verified Knowledge Base ({docs.length} documents)</h3>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Crop / Region</th>
                <th>Source</th>
                <th>Version</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.doc_id}>
                  <td>{d.title}</td>
                  <td>{d.crop || "All"} / {d.region || "All India"}</td>
                  <td>{d.publisher}</td>
                  <td>{d.version}</td>
                  <td><span className={`pill ${d.approval_status === "rejected" ? "refuse" : ""}`}>{d.approval_status}</span></td>
                  <td>{d.chunk_count}</td>
                  <td className="row">
                    <button className="btn secondary" onClick={() => setDocApproval(d.doc_id, "approved")}>Approve</button>
                    <button className="btn danger" onClick={() => setDocApproval(d.doc_id, "rejected")}>Reject</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "glossary" && (
        <div className="card">
          <h3>Multilingual Agricultural Glossary ({terms.length} terms)</h3>
          <form className="row" onSubmit={addGlossaryTerm} style={{ marginBottom: 14 }}>
            <select className="select" value={newTerm.category} onChange={(e) => setNewTerm({ ...newTerm, category: e.target.value })}>
              <option value="crop">Crop</option>
              <option value="pest">Pest</option>
              <option value="chemical">Chemical</option>
              <option value="scheme">Scheme</option>
            </select>
            <input className="input" placeholder="English" value={newTerm.en} onChange={(e) => setNewTerm({ ...newTerm, en: e.target.value })} />
            <input className="input" placeholder="Hindi" value={newTerm.hi} onChange={(e) => setNewTerm({ ...newTerm, hi: e.target.value })} />
            <input className="input" placeholder="Marathi" value={newTerm.mr} onChange={(e) => setNewTerm({ ...newTerm, mr: e.target.value })} />
            <button className="btn" type="submit">Add Term</button>
          </form>
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>English</th>
                <th>Hindi</th>
                <th>Marathi</th>
              </tr>
            </thead>
            <tbody>
              {terms.map((t) => (
                <tr key={t.term_id}>
                  <td>{t.category}</td>
                  <td>{t.en}</td>
                  <td>{t.hi}</td>
                  <td>{t.mr}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "eval" && (
        <div>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h3>Automated Evaluation Suite</h3>
              <button className="btn" onClick={runEvalSuite} disabled={loading}>
                {loading ? "Running..." : "Run Benchmark"}
              </button>
            </div>
            {evalSummary && (
              <div className="grid-4" style={{ marginTop: 14 }}>
                <div className="stat-box">
                  <div className="stat-val">{(evalSummary.retrieval_recall_at_5 * 100).toFixed(1)}%</div>
                  <div className="stat-lbl">Retrieval Recall@5 (Target &ge; 85%)</div>
                </div>
                <div className="stat-box">
                  <div className="stat-val">{(evalSummary.mean_faithfulness * 100).toFixed(1)}%</div>
                  <div className="stat-lbl">Faithfulness (Target &ge; 90%)</div>
                </div>
                <div className="stat-box">
                  <div className="stat-val">{(evalSummary.refusal_accuracy * 100).toFixed(1)}%</div>
                  <div className="stat-lbl">Safe Refusal (Target &ge; 90%)</div>
                </div>
                <div className="stat-box">
                  <div className="stat-val">{evalSummary.latency_p95_ms} ms</div>
                  <div className="stat-lbl">p95 Latency (Target &lt; 15s)</div>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <h3>Expert Review Queue ({reviewQueue.length} items)</h3>
            <table>
              <thead>
                <tr>
                  <th>Lang</th>
                  <th>Transcript</th>
                  <th>Decision</th>
                  <th>Reason</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {reviewQueue.map((item) => (
                  <tr key={item.interaction_id}>
                    <td>{item.language}</td>
                    <td>{item.transcript}</td>
                    <td>{item.decision}</td>
                    <td>{item.reason_code}</td>
                    <td>{(item.confidence * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
