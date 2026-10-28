import { useState, useEffect, useCallback, useRef } from "react";

// ─── API CONFIG ───────────────────────────────────────────────────────────────
const API_BASE = window.MOMOSHIELD_API_BASE || "http://127.0.0.1:8000/api";

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "X-CSRFToken": getCsrfToken(), ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || err.detail || res.statusText);
  }
  return res.json();
}

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

// ─── CONSTANTS ────────────────────────────────────────────────────────────────
const NAV = [
  { id: "dashboard", label: "Dashboard",    icon: "⬡" },
  { id: "transactions", label: "Transactions", icon: "⇄" },
  { id: "alerts",   label: "Fraud Alerts",  icon: "◈" },
  { id: "upload",   label: "Upload Data",   icon: "↑" },
  { id: "reports",  label: "Reports",       icon: "▦" },
];

const riskColor = (p) => p >= 0.75 ? "#ff3c3c" : p >= 0.40 ? "#ffaa00" : "#00d68f";
const riskLabel = (p) => p >= 0.75 ? "HIGH" : p >= 0.40 ? "MEDIUM" : "LOW";
const fmtUGX = (n) => `UGX ${Number(n).toLocaleString()}`;
const fmtPct = (n) => `${(n * 100).toFixed(1)}%`;

// ─── UI PRIMITIVES ────────────────────────────────────────────────────────────
const Card = ({ children, style = {} }) => (
  <div style={{
    background: "#0d1620", border: "1px solid #1a2535",
    borderRadius: 12, padding: "20px 22px", ...style
  }}>{children}</div>
);

const StatCard = ({ label, value, color, sub }) => (
  <Card>
    <div style={{ fontSize: 11, color: "#4a6080", textTransform: "uppercase",
      letterSpacing: "0.8px", marginBottom: 8 }}>{label}</div>
    <div style={{ fontSize: 26, fontWeight: 700, color, fontFamily: "monospace" }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color: "#4a6080", marginTop: 4 }}>{sub}</div>}
  </Card>
);

const Badge = ({ level }) => {
  const c = level === "high" ? "#ff3c3c" : level === "medium" ? "#ffaa00" : "#00d68f";
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4,
      background: `${c}18`, border: `1px solid ${c}33`, color: c
    }}>{level?.toUpperCase()}</span>
  );
};

const Spinner = () => (
  <div style={{ textAlign: "center", padding: 40, color: "#4a6080" }}>
    <div style={{
      width: 32, height: 32, border: "3px solid #1a2535",
      borderTop: "3px solid #00d68f", borderRadius: "50%",
      animation: "spin 0.8s linear infinite", margin: "0 auto 12px"
    }} />
    Loading...
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
);

const DonutRing = ({ pct, color, size = 80 }) => {
  const r = 32, c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox="0 0 80 80">
      <circle cx="40" cy="40" r={r} fill="none" stroke="#1e2a38" strokeWidth="10" />
      <circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="10"
        strokeDasharray={`${(pct / 100) * c} ${c}`} strokeLinecap="round"
        transform="rotate(-90 40 40)" style={{ transition: "stroke-dasharray 1s ease" }} />
      <text x="40" y="45" textAnchor="middle" fill={color} fontSize="14"
        fontWeight="bold" fontFamily="monospace">{pct}%</text>
    </svg>
  );
};

// ─── DASHBOARD PAGE ───────────────────────────────────────────────────────────
function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiFetch("/stats/")
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox msg={error} />;

  const { total_transactions, fraud_count, fraud_rate, avg_fraud_probability,
    by_transaction_type, recent_jobs } = stats;

  return (
    <div>
      <PageHeader title="Dashboard" sub="Real-time fraud detection overview" />

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard label="Total Transactions" value={total_transactions.toLocaleString()} color="#0099ff" />
        <StatCard label="Fraud Detected" value={fraud_count.toLocaleString()} color="#ff3c3c"
          sub={`${fraud_rate}% of total`} />
        <StatCard label="Legitimate" value={(total_transactions - fraud_count).toLocaleString()} color="#00d68f" />
        <StatCard label="Avg Fraud Score" value={`${avg_fraud_probability}%`} color="#ffaa00" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {/* Fraud rate donut */}
        <Card>
          <SectionTitle>Fraud vs Legitimate</SectionTitle>
          <div style={{ display: "flex", alignItems: "center", gap: 32, padding: "8px 0" }}>
            <DonutRing pct={Math.round(fraud_rate)} color="#ff3c3c" size={100} />
            <div>
              <LegendItem color="#ff3c3c" label="Fraud" value={fraud_count} />
              <LegendItem color="#00d68f" label="Legitimate" value={total_transactions - fraud_count} />
            </div>
          </div>
        </Card>

        {/* By transaction type */}
        <Card>
          <SectionTitle>By Transaction Type</SectionTitle>
          {by_transaction_type.slice(0, 6).map(r => (
            <div key={r.transaction_type} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between",
                fontSize: 11, color: "#8899aa", marginBottom: 3 }}>
                <span>{r.transaction_type}</span>
                <span>{r.fraud} fraud / {r.total}</span>
              </div>
              <div style={{ height: 6, background: "#1a2535", borderRadius: 3 }}>
                <div style={{
                  height: "100%", borderRadius: 3,
                  width: `${(r.total / (by_transaction_type[0]?.total || 1)) * 100}%`,
                  background: r.fraud > 0
                    ? "linear-gradient(90deg,#0099ff,#ff3c3c)"
                    : "linear-gradient(90deg,#0099ff,#00d68f)"
                }} />
              </div>
            </div>
          ))}
        </Card>
      </div>

      {/* Recent jobs */}
      <Card>
        <SectionTitle>Recent Detection Jobs</SectionTitle>
        {recent_jobs.length === 0
          ? <EmptyState msg="No detection jobs yet. Upload a CSV to get started." />
          : recent_jobs.map(j => (
            <div key={j.id} style={{
              display: "flex", justifyContent: "space-between",
              padding: "10px 0", borderBottom: "1px solid #1a2535"
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#cdd9e5" }}>{j.original_filename}</div>
                <div style={{ fontSize: 11, color: "#4a6080" }}>
                  {j.total_records.toLocaleString()} records · {j.fraud_count} fraud ({j.fraud_rate}%)
                </div>
              </div>
              <StatusBadge status={j.status} />
            </div>
          ))
        }
      </Card>
    </div>
  );
}

// ─── TRANSACTIONS PAGE ────────────────────────────────────────────────────────
function TransactionsPage() {
  const [transactions, setTxns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");

  const load = useCallback(() => {
    setLoading(true);
    const q = filter === "fraud" ? "?fraud=true" : filter === "clean" ? "?fraud=false" : "";
    apiFetch(`/transactions/${q}`)
      .then(d => setTxns(d.results || d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <PageHeader title="Transactions" sub="All processed transactions" />
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {["all", "fraud", "clean"].map(f => (
          <FilterBtn key={f} active={filter === f} onClick={() => setFilter(f)}>
            {f === "all" ? "All" : f === "fraud" ? "🚨 Fraud Only" : "✅ Legitimate"}
          </FilterBtn>
        ))}
      </div>
      {loading ? <Spinner /> : error ? <ErrorBox msg={error} /> : (
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#090f18" }}>
                {["ID", "Sender", "Receiver", "Amount", "Type", "Score", "Risk", "Status"].map(h => (
                  <Th key={h}>{h}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {transactions.length === 0
                ? <tr><td colSpan={8} style={{ textAlign: "center", padding: 40, color: "#4a6080" }}>
                    No transactions found
                  </td></tr>
                : transactions.slice(0, 200).map(t => (
                  <tr key={t.transaction_id} style={{
                    borderBottom: "1px solid #1a2535",
                    background: t.is_fraud ? "rgba(255,60,60,0.03)" : "transparent"
                  }}>
                    <Td mono>{t.transaction_id}</Td>
                    <Td mono small>{t.sender}</Td>
                    <Td mono small>{t.receiver}</Td>
                    <Td mono>{fmtUGX(t.amount)}</Td>
                    <Td>{t.transaction_type}</Td>
                    <Td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <div style={{ flex: 1, height: 4, background: "#1a2535", borderRadius: 2 }}>
                          <div style={{
                            height: "100%", borderRadius: 2,
                            width: `${(t.fraud_probability || 0) * 100}%`,
                            background: riskColor(t.fraud_probability || 0)
                          }} />
                        </div>
                        <span style={{ fontSize: 10, fontFamily: "monospace",
                          color: riskColor(t.fraud_probability || 0) }}>
                          {fmtPct(t.fraud_probability || 0)}
                        </span>
                      </div>
                    </Td>
                    <Td><Badge level={t.risk_level} /></Td>
                    <Td>
                      {t.is_fraud
                        ? <span style={{ color: "#ff3c3c", fontWeight: 700, fontSize: 11 }}>FRAUD</span>
                        : <span style={{ color: "#00d68f", fontSize: 11 }}>CLEAN</span>}
                    </Td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ─── ALERTS PAGE ──────────────────────────────────────────────────────────────
function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sev, setSev] = useState("all");

  useEffect(() => {
    const q = sev !== "all" ? `?severity=${sev}` : "";
    apiFetch(`/alerts/${q}`)
      .then(d => setAlerts(d.results || d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [sev]);

  return (
    <div>
      <PageHeader title="Fraud Alerts" sub="Flagged transactions requiring review" />
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {["all", "high", "medium", "low"].map(s => (
          <FilterBtn key={s} active={sev === s} onClick={() => setSev(s)}>
            {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
          </FilterBtn>
        ))}
      </div>
      {loading ? <Spinner /> : error ? <ErrorBox msg={error} /> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {alerts.length === 0
            ? <EmptyState msg="No fraud alerts. Upload a CSV to run detection." />
            : alerts.slice(0, 100).map((a, i) => (
              <Card key={i} style={{ borderLeft: `3px solid ${riskColor(a.severity === "high" ? 0.9 : a.severity === "medium" ? 0.55 : 0.1)}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                      <Badge level={a.severity} />
                      <span style={{ fontSize: 12, fontFamily: "monospace", color: "#8899aa" }}>
                        {a.transaction?.transaction_id}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: "#cdd9e5", marginBottom: 4 }}>{a.reason}</div>
                    <div style={{ fontSize: 11, color: "#4a6080" }}>{a.transaction?.transaction_type} · {fmtUGX(a.transaction?.amount)}</div>
                  </div>
                  <div style={{ fontSize: 10, color: "#4a6080" }}>
                    {a.reviewed ? "✅ Reviewed" : "⏳ Pending"}
                  </div>
                </div>
              </Card>
            ))}
        </div>
      )}
    </div>
  );
}

// ─── UPLOAD PAGE ──────────────────────────────────────────────────────────────
function UploadPage({ onJobComplete }) {
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef();

  const handleFile = (f) => {
    if (f && f.name.endsWith(".csv")) {
      setFile(f);
      setResult(null);
      setError(null);
    } else {
      setError("Please select a valid .csv file");
    }
  };

  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true);
    setProgress(10);
    setError(null);

    const fd = new FormData();
    fd.append("file", file);

    // Simulate progress while waiting
    const interval = setInterval(() => {
      setProgress(p => Math.min(p + 8, 85));
    }, 400);

    try {
      const data = await apiFetch("/detect/upload/", { method: "POST", body: fd });
      clearInterval(interval);
      setProgress(100);
      setResult(data);
      if (onJobComplete) onJobComplete();
    } catch (e) {
      clearInterval(interval);
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <PageHeader title="Upload Transaction Data" sub="Upload a CSV file to run real fraud detection" />
      <div style={{ maxWidth: 620 }}>
        {!result ? (
          <>
            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={e => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
              onClick={() => inputRef.current?.click()}
              style={{
                border: `2px dashed ${drag ? "#0099ff" : file ? "#00d68f" : "#1a2535"}`,
                borderRadius: 16, padding: "50px 40px", textAlign: "center",
                background: drag ? "rgba(0,153,255,0.05)" : "#0d1620",
                transition: "all 0.2s", cursor: "pointer", marginBottom: 20,
              }}>
              <input ref={inputRef} type="file" accept=".csv" style={{ display: "none" }}
                onChange={e => handleFile(e.target.files[0])} />
              <div style={{ fontSize: 36, marginBottom: 12 }}>{file ? "📄" : "📂"}</div>
              {file
                ? <div style={{ fontSize: 14, fontWeight: 600, color: "#00d68f" }}>{file.name}
                    <div style={{ fontSize: 11, color: "#4a6080", marginTop: 4 }}>
                      {(file.size / 1024).toFixed(1)} KB · Click to change
                    </div>
                  </div>
                : <>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#cdd9e5", marginBottom: 6 }}>
                      Drag & drop your CSV file here
                    </div>
                    <div style={{ fontSize: 12, color: "#4a6080", marginBottom: 16 }}>
                      Supports: .csv · Max 100MB
                    </div>
                    <button style={{
                      padding: "9px 24px", borderRadius: 8,
                      background: "linear-gradient(90deg,#0099ff,#00d68f)",
                      border: "none", color: "#080f18", fontWeight: 700, fontSize: 13, cursor: "pointer"
                    }}>Browse Files</button>
                  </>}
            </div>

            {/* Required columns hint */}
            <Card style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, color: "#4a6080", marginBottom: 8,
                textTransform: "uppercase", letterSpacing: "0.6px" }}>Expected CSV Columns</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {["txn_id","sender","receiver","amount_ugx","txn_type","time","day_of_week",
                  "is_weekend","hour","channel","sender_account_age_days","receiver_account_age_days",
                  "is_new_receiver","sender_txn_count_1h","sender_txn_count_24h",
                  "amount_deviation","receiver_previously_flagged","round_amount"].map(c => (
                  <span key={c} style={{
                    fontSize: 10, fontFamily: "monospace", padding: "2px 8px",
                    background: "rgba(0,153,255,0.08)", border: "1px solid rgba(0,153,255,0.2)",
                    borderRadius: 4, color: "#0099ff"
                  }}>{c}</span>
                ))}
              </div>
            </Card>

            {error && <ErrorBox msg={error} />}

            {uploading && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between",
                  fontSize: 11, color: "#4a6080", marginBottom: 6 }}>
                  <span>Running fraud detection...</span>
                  <span>{progress}%</span>
                </div>
                <div style={{ height: 6, background: "#1a2535", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 3,
                    width: `${progress}%`,
                    background: "linear-gradient(90deg,#0099ff,#00d68f)",
                    transition: "width 0.4s ease"
                  }} />
                </div>
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={!file || uploading}
              style={{
                width: "100%", padding: "12px 0", borderRadius: 10,
                background: file && !uploading
                  ? "linear-gradient(90deg,#0099ff22,#00d68f22)"
                  : "#1a2535",
                border: `1px solid ${file && !uploading ? "#0099ff44" : "#1a2535"}`,
                color: file && !uploading ? "#00d68f" : "#4a6080",
                fontWeight: 700, fontSize: 14,
                cursor: file && !uploading ? "pointer" : "not-allowed",
              }}>
              {uploading ? "⚙ Analysing transactions..." : "▶ Run Fraud Detection"}
            </button>
          </>
        ) : (
          <ResultCard result={result} onReset={() => { setFile(null); setResult(null); }} />
        )}
      </div>
    </div>
  );
}

function ResultCard({ result, onReset }) {
  const s = result.processing_log || {};
  return (
    <Card style={{ textAlign: "center" }}>
      <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#00d68f", marginBottom: 6 }}>
        Detection Complete
      </div>
      <div style={{ fontSize: 12, color: "#5a7090", marginBottom: 24 }}>
        {result.original_filename}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "Total Scanned",  val: result.total_records?.toLocaleString(), color: "#0099ff" },
          { label: "Fraud Flagged",  val: result.fraud_count?.toLocaleString(),   color: "#ff3c3c" },
          { label: "Fraud Rate",     val: `${result.fraud_rate}%`,                color: "#ffaa00" },
        ].map((st, i) => (
          <div key={i} style={{ background: "#090f18", borderRadius: 10, padding: "14px 16px" }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: st.color, fontFamily: "monospace" }}>{st.val}</div>
            <div style={{ fontSize: 10, color: "#4a6080", marginTop: 4 }}>{st.label}</div>
          </div>
        ))}
      </div>
      {s.high_risk_count > 0 && (
        <div style={{ background: "rgba(255,60,60,0.06)", border: "1px solid #ff3c3c22",
          borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 12, color: "#ff9999" }}>
          ⚠ {s.high_risk_count} high-risk transactions detected
        </div>
      )}
      <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
        <button onClick={onReset} style={{
          padding: "9px 20px", borderRadius: 8, border: "1px solid #1a2535",
          background: "transparent", color: "#5a7090", fontSize: 12, cursor: "pointer"
        }}>Upload Another</button>
      </div>
    </Card>
  );
}

// ─── REPORTS PAGE ─────────────────────────────────────────────────────────────
function ReportsPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiFetch("/detect/jobs/")
      .then(d => setJobs(d.results || d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const download = (jobId, fmt) => {
    window.open(`${API_BASE.replace("/api", "")}/reports/${jobId}/export/?format=${fmt}`, "_blank");
  };

  return (
    <div>
      <PageHeader title="Reports" sub="Download fraud analysis reports" />
      {loading ? <Spinner /> : error ? <ErrorBox msg={error} /> : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {jobs.length === 0
            ? <div style={{ gridColumn: "span 2" }}><EmptyState msg="No completed detection jobs yet." /></div>
            : jobs.filter(j => j.status === "done").map(j => (
              <Card key={j.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#cdd9e5", marginBottom: 4 }}>
                    {j.original_filename}
                  </div>
                  <div style={{ fontSize: 11, color: "#4a6080" }}>
                    Job #{j.id} · {j.total_records.toLocaleString()} records · {j.fraud_count} fraud
                  </div>
                  <div style={{ fontSize: 10, color: "#4a6080", marginTop: 2 }}>
                    {new Date(j.created_at).toLocaleDateString("en-UG")}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <ExportBtn color="#ff3c3c" label="PDF"   onClick={() => download(j.id, "pdf")} />
                  <ExportBtn color="#00d68f" label="Excel" onClick={() => download(j.id, "excel")} />
                </div>
              </Card>
            ))}
        </div>
      )}
    </div>
  );
}

// ─── SHARED MICRO-COMPONENTS ──────────────────────────────────────────────────
const PageHeader = ({ title, sub }) => (
  <div style={{ marginBottom: 24 }}>
    <h1 style={{ fontSize: 20, fontWeight: 700, color: "#e8f0fb", margin: 0 }}>{title}</h1>
    {sub && <p style={{ fontSize: 12, color: "#4a6080", margin: "4px 0 0" }}>{sub}</p>}
  </div>
);

const SectionTitle = ({ children }) => (
  <div style={{ fontSize: 11, color: "#4a6080", textTransform: "uppercase",
    letterSpacing: "0.8px", marginBottom: 14 }}>{children}</div>
);

const LegendItem = ({ color, label, value }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
    <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
    <span style={{ fontSize: 12, color: "#8899aa" }}>{label}</span>
    <span style={{ fontSize: 12, fontWeight: 600, color: "#cdd9e5", marginLeft: "auto" }}>
      {value?.toLocaleString()}
    </span>
  </div>
);

const ErrorBox = ({ msg }) => (
  <div style={{
    background: "rgba(255,60,60,0.08)", border: "1px solid #ff3c3c33",
    borderRadius: 10, padding: "12px 16px", fontSize: 13, color: "#ff8888", marginBottom: 16
  }}>⚠ {msg}</div>
);

const EmptyState = ({ msg }) => (
  <div style={{ textAlign: "center", padding: "32px 0", color: "#4a6080", fontSize: 13 }}>
    {msg}
  </div>
);

const FilterBtn = ({ active, onClick, children }) => (
  <button onClick={onClick} style={{
    padding: "7px 16px", borderRadius: 8, border: `1px solid ${active ? "#0099ff55" : "#1a2535"}`,
    background: active ? "rgba(0,153,255,0.12)" : "transparent",
    color: active ? "#0099ff" : "#5a7090", fontSize: 12, cursor: "pointer", fontWeight: active ? 600 : 400
  }}>{children}</button>
);

const StatusBadge = ({ status }) => {
  const c = status === "done" ? "#00d68f" : status === "failed" ? "#ff3c3c" : "#ffaa00";
  return (
    <span style={{
      fontSize: 10, padding: "2px 8px", borderRadius: 4,
      background: `${c}18`, border: `1px solid ${c}33`, color: c, fontWeight: 700
    }}>{status.toUpperCase()}</span>
  );
};

const Th = ({ children }) => (
  <th style={{ padding: "10px 14px", textAlign: "left", fontSize: 10,
    color: "#4a6080", textTransform: "uppercase", letterSpacing: "0.6px",
    borderBottom: "1px solid #1a2535", whiteSpace: "nowrap" }}>{children}</th>
);

const Td = ({ children, mono, small }) => (
  <td style={{ padding: "10px 14px", fontSize: small ? 11 : 12,
    color: "#cdd9e5", fontFamily: mono ? "monospace" : "inherit",
    borderBottom: "1px solid #0d1620" }}>{children}</td>
);

const ExportBtn = ({ color, label, onClick }) => (
  <button onClick={onClick} style={{
    padding: "7px 14px", borderRadius: 7, fontSize: 11, fontWeight: 700,
    background: `${color}18`, border: `1px solid ${color}33`, color, cursor: "pointer"
  }}>↓ {label}</button>
);

// ─── ROOT APP ─────────────────────────────────────────────────────────────────
export default function MoMoShield() {
  const [active, setActive] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const pages = {
    dashboard: <DashboardPage key={refreshKey} />,
    transactions: <TransactionsPage />,
    alerts: <AlertsPage />,
    upload: <UploadPage onJobComplete={() => setRefreshKey(k => k + 1)} />,
    reports: <ReportsPage />,
  };

  return (
    <div style={{
      display: "flex", height: "100vh", background: "#080f18",
      fontFamily: "'DM Sans','Segoe UI',sans-serif", color: "#cdd9e5", overflow: "hidden"
    }}>
      {/* Sidebar */}
      <div style={{
        width: sidebarOpen ? 220 : 64, minWidth: sidebarOpen ? 220 : 64,
        background: "#0d1620", borderRight: "1px solid #1a2535",
        display: "flex", flexDirection: "column", transition: "width 0.3s ease",
        overflow: "hidden", zIndex: 10
      }}>
        {/* Logo */}
        <div style={{ padding: "24px 16px 20px", borderBottom: "1px solid #1a2535",
          display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg,#00d68f,#0099ff)",
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0, fontSize: 16, fontWeight: "bold", color: "#080f18"
          }}>M</div>
          {sidebarOpen && (
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#e8f0fb" }}>MoMo Shield</div>
              <div style={{ fontSize: 10, color: "#4a6080", letterSpacing: "1.5px", textTransform: "uppercase" }}>
                Fraud Detection
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "12px 8px" }}>
          {NAV.map(item => (
            <button key={item.id} onClick={() => setActive(item.id)} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 12,
              padding: "10px 12px", borderRadius: 8, border: "none", cursor: "pointer",
              background: active === item.id
                ? "linear-gradient(90deg,rgba(0,214,143,.12),rgba(0,153,255,.08))"
                : "transparent",
              color: active === item.id ? "#00d68f" : "#5a7090",
              marginBottom: 2, transition: "all 0.2s",
              borderLeft: active === item.id ? "2px solid #00d68f" : "2px solid transparent",
              textAlign: "left", whiteSpace: "nowrap", overflow: "hidden"
            }}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>{item.icon}</span>
              {sidebarOpen && <span style={{ fontSize: 13, fontWeight: 500 }}>{item.label}</span>}
            </button>
          ))}
        </nav>

        {/* Collapse toggle */}
        <div style={{ padding: "12px 8px", borderTop: "1px solid #1a2535" }}>
          <button onClick={() => setSidebarOpen(o => !o)} style={{
            width: "100%", padding: "8px 12px", borderRadius: 8, border: "none",
            background: "transparent", color: "#4a6080", cursor: "pointer",
            fontSize: 16, textAlign: "left"
          }}>
            {sidebarOpen ? "◀" : "▶"}
          </button>
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>
        {pages[active]}
      </div>
    </div>
  );
}
