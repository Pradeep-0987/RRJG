import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import "./styles.css";

const API = `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;

async function api(path, opts = {}) {
  const token = localStorage.getItem("token");
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(API + path, { ...opts, headers });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(data.detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function Header({ title, sub }) {
  return <header><div><h1>{title}</h1><p>{sub}</p></div><div className="status">● System online</div></header>;
}

function Badge({ x }) {
  const cls = String(x || "WATCH").toLowerCase();
  return <span className={`badge ${cls}`}>{x}</span>;
}

function Login() {
  const [email, setEmail] = useState("owner@retailpulse.ai");
  const [password, setPassword] = useState("owner123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const x = await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      localStorage.setItem("token", x.access_token);
      localStorage.setItem("role", x.role);
      nav("/", { replace: true });
    } catch (e) {
      setError(e.message || "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  }

  const capabilityCards = [
    ["01","FORECAST","ARIMA + LSTM demand intelligence"],
    ["02","INVENTORY","Stock risk & replenishment"],
    ["03","ANALYTICS","Daily → yearly performance"],
    ["04","COPILOT","Grounded AI decisions"],
    ["05","CONTROL","Enterprise roles & access"]
  ];

  return <div className="login-shell">
    <div className="login-noise"/>
    <div className="login-orbit orbit-1"/><div className="login-orbit orbit-2"/>
    <section className="login-visual">
      <div className="login-brand-lockup">
        <div className="brand-symbol">R<span>AI</span></div>
        <div><b>RetailPulse AI</b><small>RETAIL INTELLIGENCE PLATFORM</small></div>
      </div>
      <div className="login-hero-copy">
        <div className="eyebrow">AI OPERATING SYSTEM FOR RETAIL</div>
        <h1>Turn retail data into <span>decisions.</span></h1>
        <p>Forecast demand, understand inventory risk, automate replenishment and ask your retail data questions with grounded AI.</p>
      </div>
      <div className="login-capabilities">
        {capabilityCards.map(([n,title,desc],i)=><div className={`cap-card cap-${i+1}`} key={n}>
          <div className="cap-number">{n}</div>
          <div className="mini-robot"><i/><i/><i/></div>
          <b>{title}</b><span>{desc}</span>
        </div>)}
      </div>
      <div className="login-footnote">Built for data-driven retail teams · Secure workspace · Explainable intelligence</div>
    </section>

    <section className="login-panel">
      <div className="login-panel-inner">
        <div className="mobile-brand"><div className="brand-symbol">R<span>AI</span></div><b>RetailPulse AI</b></div>
        <div className="login-kicker">WELCOME BACK</div>
        <h2>Sign in to your workspace</h2>
        <p className="login-subtitle">Access your forecasts, inventory intelligence and AI Copilot.</p>

        <div className="login-tabs"><span className="selected">Sign in</span><span>Create account</span></div>

        <form onSubmit={submit} className="login-form">
          <label>Work email<input autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com"/></label>
          <label>Password<div className="password-wrap"><input autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password"/><span>•••</span></div></label>
          <div className="login-options"><label className="remember"><input type="checkbox"/> <span>Remember me</span></label><span>Secure access</span></div>
          <button className="login-submit" disabled={loading}>{loading ? "Signing in…" : <>Sign in <span>→</span></>}</button>
        </form>

        {error && <div className="error login-error">{error}</div>}
        <div className="demo-box"><span>DEMO WORKSPACE</span><b>owner@retailpulse.ai</b><small>owner123</small></div>
        <div className="login-legal">By continuing, you agree to your organization's workspace policies.</div>
      </div>
    </section>
  </div>;
}

function RequireAuth({ children }) {
  return localStorage.getItem("token") ? children : <Navigate to="/login" replace />;
}

const links = [
  ["/", "Command Center", "dashboard", "⌂"], ["/products", "Products", "products", "◈"], ["/data", "Data Intelligence", "data_upload", "▦"],
  ["/studio", "Forecast Studio", "forecasts", "◒"], ["/arima", "ARIMA Lab", "arima", "∿"], ["/lstm", "LSTM Lab", "lstm", "⌁"],
  ["/evaluation", "Model Evaluation", "model_center", "◎"], ["/seasonality", "Seasonality & Anomalies", "seasonality", "◌"],
  ["/inventory", "Inventory Intelligence", "inventory", "▥"], ["/restock-center", "Restock Center", "restock", "↗"],
  ["/scenarios", "Scenario Planner", "scenarios", "◇"], ["/alerts", "Action Center", "alerts", "!"],
  ["/reports", "Reports & Analytics", "reports", "▤"], ["/copilot", "Retail Copilot", "copilot", "✦"]
];

function AmbientScene(){return <div className="ambient-scene" aria-hidden="true"><div className="orb orb-a"/><div className="orb orb-b"/><div className="orb orb-c"/><div className="ring ring-a"/><div className="ring ring-b"/><div className="cube cube-a"/><div className="cube cube-b"/><div className="grid-floor"/></div>}

function CopilotWidget(){
  const [open,setOpen]=useState(false),[q,setQ]=useState("Which products should I restock?"),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  async function ask(){if(!q.trim())return;setLoading(true);setError("");try{setR(await api("/copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})}))}catch(e){setError(e.message)}finally{setLoading(false)}}
  return <><button className="copilot-fab" onClick={()=>setOpen(v=>!v)} aria-label="Open Retail Copilot"><span className="spark">✦</span><span>AI Copilot</span></button>{open&&<section className="copilot-drawer"><div className="copilot-head"><div><b>Retail Copilot</b><small>Grounded in your store data</small></div><button className="icon-btn" onClick={()=>setOpen(false)}>×</button></div><div className="suggestions">{["Which products should I restock?","What is my demand trend?","Which products are at risk?","How accurate are my forecasts?"].map(x=><button className="chip" key={x} onClick={()=>setQ(x)}>{x}</button>)}</div><div className="copilot-input"><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')ask()}}/><button onClick={ask} disabled={loading}>{loading?"…":"→"}</button></div>{error&&<div className="error">{error}</div>}{r&&<div className="copilot-answer"><div className="answer-label">AI INSIGHT</div><p>{r.answer}</p><div className="source-row">Sources: {(r.sources||[]).join(" · ")}</div><div className="copilot-action">{r.action}</div></div>}</section>}</>
}

function Layout({ children }) {
  const [me,setMe]=useState(null),[permissions,setPermissions]=useState([]),[dbStatus,setDbStatus]=useState("checking"),[dark,setDark]=useState(localStorage.getItem("theme")==="dark"),[mobileOpen,setMobileOpen]=useState(false);
  const nav=useNavigate(),location=useLocation();
  useEffect(()=>{api("/auth/me").then(setMe).catch(()=>{});api("/auth/permissions").then(x=>setPermissions(x.permissions||[])).catch(()=>{});api("/health").then(x=>setDbStatus(x.database||"connected")).catch(()=>setDbStatus("offline"))},[]);
  useEffect(()=>{document.documentElement.dataset.theme=dark?"dark":"light";localStorage.setItem("theme",dark?"dark":"light")},[dark]);
  useEffect(()=>setMobileOpen(false),[location.pathname]);
  function signOut(){localStorage.removeItem("token");localStorage.removeItem("role");nav("/login",{replace:true})}
  const visible=links.filter(([, ,perm])=>permissions.includes(perm));
  return <div className="app"><AmbientScene/>
    <button className="mobile-menu" onClick={()=>setMobileOpen(v=>!v)} aria-label="Toggle navigation">☰</button>
    {mobileOpen&&<div className="nav-backdrop" onClick={()=>setMobileOpen(false)}/>} 
    <aside className={mobileOpen?"sidebar-open":""}>
      <div className="brand-mark" onClick={()=>nav("/")} role="button" tabIndex="0"><span>R</span><div><b>RetailPulse <em>AI</em></b><small>AI RETAIL OPERATING PLATFORM</small></div></div>
      {me&&<div className="identity"><span className="online-dot"/><div><b>{me.role}</b><small>{me.store?.name||"Store"}</small></div></div>}
      <div className="sidebar-scroll">
        <div className="nav-label">Workspace</div>
        <nav className="side-nav">{visible.map(([u,label,perm,icon])=><Link key={u} to={u} title={label} className={location.pathname===u?"active":""}><span className="nav-icon">{icon}</span><span>{label}</span>{location.pathname===u&&<i className="nav-active-dot"/>}</Link>)}</nav>
        {permissions.includes("settings")&&<><div className="nav-label">Administration</div><nav className="side-nav"><Link to="/settings" className={location.pathname==="/settings"?"active":""}><span className="nav-icon">⚙</span><span>Settings & Access</span>{location.pathname==="/settings"&&<i className="nav-active-dot"/>}</Link></nav></>}
      </div>
      <div className="side-bottom"><button onClick={()=>setDark(v=>!v)}>{dark?"☀  Light mode":"☾  Dark mode"}</button><button onClick={signOut}>↪  Sign out</button></div>
    </aside>
    <main><div className="topbar"><div className="breadcrumbs"><b>RetailPulse AI</b><span>/</span>{me?.store?.name||"Store"}</div><div className="top-actions"><span className="system-pill"><i/> {dbStatus === "offline" ? "Database offline" : dbStatus === "checking" ? "Checking database" : "PostgreSQL connected"}</span>{permissions.includes("copilot")&&<Link className="top-copilot" to="/copilot">✦ Copilot</Link>}</div></div>{children}</main>
    {permissions.includes("copilot")&&<CopilotWidget/>}
  </div>;
}

function RoleGate({permission,children}){const [allowed,setAllowed]=useState(null);useEffect(()=>{api("/auth/permissions").then(x=>setAllowed((x.permissions||[]).includes(permission))).catch(()=>setAllowed(false))},[permission]);if(allowed===null)return <Layout><div className="loading">Checking access…</div></Layout>;if(!allowed)return <Layout><Header title="Access restricted" sub="Your role does not have access to this feature."/><div className="access-denied"><div className="access-icon">🔒</div><h2>Permission required</h2><p>Ask the workspace owner to grant access if you need this capability.</p></div></Layout>;return children;}

function useLoad(path, deps = []) {
  const [data, setData] = useState(null), [error, setError] = useState(""), [loading, setLoading] = useState(true);
  useEffect(() => { let alive = true; setLoading(true); api(path).then(x => alive && setData(x)).catch(e => alive && setError(e.message)).finally(() => alive && setLoading(false)); return () => { alive = false; }; }, deps);
  return { data, error, loading, setData };
}

function Dashboard() {
  const { data: d, error, loading } = useLoad("/dashboard", []);
  if (loading) return <Layout><div className="loading">Loading KPI intelligence…</div></Layout>;
  if (error) return <Layout><Header title="Command Center" sub="Dashboard"/><div className="error">{error}<br/><span className="muted">Make sure the backend is running on http://127.0.0.1:8000.</span></div></Layout>;
  const k = d?.kpis || {};
  const max = Math.max(...(d?.trend || []).map(x => x.units), 1);
  return <Layout><Header title="Executive Intelligence" sub="Demand, inventory and forecasting KPIs"/>
    <div className="cards">{[["Products", k.products],["Sales Units · 30d", k.sales_units_30d],["Daily Demand", k.daily_demand_30d],["Demand Growth", k.demand_growth_pct == null ? "—" : `${k.demand_growth_pct}%`],["Stock Units", k.stock_units],["Low Stock", k.low_stock_products],["Forecast Demand", k.forecast_demand],["Avg Forecast MAPE", k.average_forecast_mape == null ? "—" : `${k.average_forecast_mape}%`]].map(([a,b]) => <div className="card" key={a}><small>{a}</small><strong>{b ?? "—"}</strong></div>)}</div>
    <div className="comparison"><div className="panel"><h2>30-Day Demand Trend</h2><div className="bar-chart">{(d?.trend || []).map(x => <div className="bar-wrap" key={x.date} title={`${x.date}: ${x.units}`}><div className="bar" style={{ height: `${Math.max(3, x.units / max * 100)}%` }} /></div>)}</div></div>
      <div className="panel"><h2>Top Products</h2><Table headers={["Product","SKU","Units"]} rows={(d?.top_products || []).map(x => [x.product,x.sku,x.units])}/></div></div>
    <div className="panel"><h2>Forecast Summary</h2><Table headers={["Product ID","Model","MAPE","Forecast Demand"]} rows={(d?.forecast_summary || []).map(x => [x.product_id,x.model,x.mape == null ? "—" : `${Number(x.mape).toFixed(2)}%`,x.forecast_total])}/></div>
  </Layout>;
}

function Table({ headers, rows }) { return <div className="table-scroll"><table><thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j}>{v}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty">No data available</td></tr>}</tbody></table></div>; }

function Products() {
  const { data, error, loading } = useLoad("/products", []);
  const [query,setQuery]=useState("");
  const [company,setCompany]=useState("ALL");
  const [category,setCategory]=useState("ALL");
  const rows=data||[];
  const companies=["ALL",...Array.from(new Set(rows.map(p=>p.company).filter(Boolean))).sort()];
  const categories=["ALL",...Array.from(new Set(rows.map(p=>p.category).filter(Boolean))).sort()];
  const filtered=rows.filter(p=>{
    const q=query.trim().toLowerCase();
    const text=`${p.name||""} ${p.brand||""} ${p.company||""} ${p.sku||""}`.toLowerCase();
    return (!q||text.includes(q))&&(company==="ALL"||p.company===company)&&(category==="ALL"||p.category===category);
  });
  if (loading) return <Layout><div className="loading">Loading global product catalog…</div></Layout>;
  return <Layout><Header title="Global Product Catalog" sub="Enterprise-ready catalog, inventory position and commercial metadata"/>
    {error&&<div className="error">{error}</div>}
    <div className="catalog-hero">
      <div><span className="eyebrow">PRODUCT MASTER DATA</span><h2>International brand portfolio</h2><p>Representative demo catalog across technology, fashion, FMCG, beauty, home and appliances. Brand names are shown for demonstration and are not endorsements.</p></div>
      <div className="catalog-count"><strong>{filtered.length}</strong><span>products</span></div>
    </div>
    <div className="catalog-toolbar">
      <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search product, brand, company or SKU…"/>
      <select value={company} onChange={e=>setCompany(e.target.value)}>{companies.map(x=><option key={x}>{x}</option>)}</select>
      <select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(x=><option key={x}>{x}</option>)}</select>
      <Link className="outline" to="/restock-center">View replenishment →</Link>
    </div>
    <div className="catalog-grid">{filtered.map(p=><article className="product premium-product" key={p.id}>
      <div className="product-company"><span>{p.company||"Imported Catalog"}</span><span className="brand-pill">{p.brand||"—"}</span></div>
      <div className="product-top"><span>{p.sku}</span><span>{p.category||"General"} · {p.subcategory||"Product"}</span></div>
      <h2>{p.name}</h2>
      <div className="price-line"><strong>{p.currency||"INR"} {Number(p.unit_price||0).toLocaleString("en-IN")}</strong><span>Unit price</span></div>
      <div className="mini"><span>Stock<b>{Number(p.current_stock||0).toLocaleString("en-IN")}</b></span><span>Safety<b>{Number(p.safety_stock||0).toLocaleString("en-IN")}</b></span><span>Lead<b>{p.lead_time_days}d</b></span></div>
      <div className="product-meta"><span>Margin</span><b>{p.unit_price&&p.unit_cost?`${Math.max(0,((p.unit_price-p.unit_cost)/p.unit_price*100)).toFixed(1)}%`:"—"}</b><span>Supplier</span><b>{p.supplier||"—"}</b></div>
      <Link className="outline" to="/restock-center">Open inventory intelligence →</Link>
    </article>)}</div>
    {!filtered.length&&<div className="empty panel">No products match your filters.</div>}
  </Layout>;
}

function Data() {
  const [file,setFile]=useState(null),[result,setResult]=useState(null),[msg,setMsg]=useState(""),[loading,setLoading]=useState(false),[clearing,setClearing]=useState(false),[me,setMe]=useState(null),[dragging,setDragging]=useState(false),[diagnostic,setDiagnostic]=useState(null);
  useEffect(()=>{api("/auth/me").then(setMe).catch(()=>{});api("/system/diagnostics").then(setDiagnostic).catch(()=>{})},[]);
  async function replaceDataset(){
    if(!file){setMsg("Choose a CSV or Excel dataset first.");return}
    if(!window.confirm("Replace ALL products, sales, forecasts and alerts for this store with this dataset? This cannot be undone."))return;
    setLoading(true);setMsg("");setResult(null);
    try{
      const fd=new FormData();fd.append("file",file);
      const endpoint=me?.role==="OWNER"?"/data/replace":"/data/upload";
      const x=await api(endpoint,{method:"POST",body:fd});
      if(x.status!=="success"){
        setResult(x);setMsg(x.message||"Dataset was analyzed but not imported. Check the required columns.");return;
      }
      const verification=await api("/system/diagnostics");
      setDiagnostic(verification);
      const expected=Number(x.products_detected||0);
      const actual=Number(verification.products||0);
      if(expected>0 && actual<expected){
        setMsg(`Import verification failed: API reported ${expected} products but the database currently has ${actual}.`);
        return;
      }
      setResult(x);
      setMsg(`Dataset imported and verified: ${actual} products and ${Number(verification.sales||0)} sales records are now in PostgreSQL.`);
    }catch(e){setMsg(e.message||"Dataset import failed. Check the backend terminal.")}finally{setLoading(false)}
  }
  async function clearDataset(){
    if(!window.confirm("DELETE ALL PRODUCTS and all related sales, forecasts and alerts for this store? This cannot be undone."))return;
    setClearing(true);setMsg("");setResult(null);
    try{const x=await api("/data/reset",{method:"POST"});setMsg(`${x.products_deleted} products removed. Upload a new dataset now.`)}catch(e){setMsg(e.message)}finally{setClearing(false)}
  }
  const a=result?.analysis;
  return <Layout><Header title="Data Intelligence" sub="Upload, analyze and manage the store dataset before forecasting"/>
    <div className="panel upload"><h2>Dataset Manager</h2><p className="muted">Upload CSV or Excel. The system validates columns, cleans records, analyzes demand, then replaces the current store dataset.</p>
      <div className="pipeline"><div><b>UPLOAD</b><br/>CSV / Excel</div><div>→</div><div><b>VALIDATE</b><br/>Columns</div><div>→</div><div><b>CLEAN</b><br/>Duplicates</div><div>→</div><div><b>ANALYZE</b><br/>Demand</div><div>→</div><div><b>READY</b><br/>ARIMA + LSTM</div></div>
      <div className={`dropzone ${dragging?"dragging":""}`}
        onDragOver={e=>{e.preventDefault();setDragging(true)}}
        onDragLeave={()=>setDragging(false)}
        onDrop={e=>{e.preventDefault();setDragging(false);const f=e.dataTransfer.files?.[0];if(f)setFile(f)}}>
        <input id="dataset-file" type="file" accept=".csv,.xlsx,.xls" onChange={e=>setFile(e.target.files?.[0]||null)}/>
        <label htmlFor="dataset-file"><span className="upload-icon">↑</span><b>{file?file.name:"Drop your retail dataset here"}</b><small>CSV, XLSX or XLS · up to 25 MB</small></label>
      </div>
      {file&&<p className="note">Selected: <b>{file.name}</b> · {Math.max(0.01,file.size/1024/1024).toFixed(2)} MB</p>}
      <div className="actions"><button onClick={replaceDataset} disabled={loading||clearing||!file}>{loading?(me?.role==="OWNER"?"Analyzing & replacing…":"Analyzing & importing…"):(me?.role==="OWNER"?"Upload & Replace Dataset":"Upload & Analyze Dataset")}</button>{me?.role==="OWNER"&&<button className="danger-btn" onClick={clearDataset} disabled={loading||clearing}>{clearing?"Removing…":"Remove All Products"}</button>}</div>
      {diagnostic&&<div className="data-db-status"><span>● PostgreSQL</span><b>{diagnostic.products??0}</b> products <b>{diagnostic.sales??0}</b> sales · schema {diagnostic.schema_ready?"ready":"needs migration"}</div>}
      {msg&&<p className={msg.includes("successfully")||msg.includes("removed")?"success":"note"}>{msg}</p>}
    </div>
    {result&&<>
      <div className="cards"><div className="card"><small>Data Health</small><strong>{result.quality?.score ?? "—"}/100</strong></div><div className="card"><small>Products</small><strong>{a?.products ?? result.products_detected}</strong></div><div className="card"><small>Sales Records</small><strong>{a?.sales_records ?? result.records_inserted}</strong></div><div className="card"><small>Total Units</small><strong>{a?.total_units ?? "—"}</strong></div><div className="card"><small>Date Range</small><strong>{a?`${a.date_start} → ${a.date_end}`:"—"}</strong></div><div className="card"><small>Forecast Ready</small><strong>{result.readiness?.ready?"YES":"NO"}</strong></div></div>
      <div className="comparison"><div className="panel"><h2>Data Quality</h2><Table headers={["Check","Score"]} rows={[["Completeness",`${result.quality?.completeness??0}%`],["Validity",`${result.quality?.validity??0}%`],["Consistency",`${result.quality?.consistency??0}%`],["Duplicates",`${result.quality?.duplicates??0}%`]]}/>{result.quality?.issues?.length>0&&<p className="note">Issues: {result.quality.issues.join(" · ")}</p>}</div><div className="panel"><h2>Forecast Readiness</h2><Table headers={["Requirement","Status"]} rows={(result.readiness?.checks||[]).map(x=>[x.name,x.passed?"✓ Passed":"✕ Needs attention"])}/><p className={result.readiness?.ready?"success":"note"}>{result.readiness?.message}</p></div></div>
      <div className="panel"><h2>Dataset Analysis</h2><p>Average daily units: <b>{a?.average_daily_units ?? "—"}</b></p><p>Products with at least 45 days of history: <b>{a?.forecast_ready_products ?? 0}</b></p><h3>Top Products</h3><Table headers={["Product","Units"]} rows={(a?.top_products||[]).map(x=>[x.product,x.units])}/></div>
    </>}
  </Layout>;
}

function ForecastStudio() {
  const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[h,setH]=useState(30),[model,setModel]=useState("AUTO"),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);
  async function run(){setLoading(true);setError("");try{setR(await api(`/forecast/studio?product_id=${pid}&horizon=${h}&model=${model}`))}catch(e){setError(e.message)}finally{setLoading(false)}}
  return <Layout><Header title="Forecast Studio" sub="Interactive demand forecasting workspace"/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><select value={model} onChange={e=>setModel(e.target.value)}><option>AUTO</option><option>ARIMA</option><option>LSTM</option></select><select value={h} onChange={e=>setH(e.target.value)}><option>7</option><option>30</option><option>60</option><option>90</option></select><button onClick={run} disabled={!pid||loading}>{loading?"Generating…":"Generate Forecast"}</button></div>{error&&<div className="error">{error}</div>}{r&&<><div className="cards"><div className="card"><small>Model</small><strong>{r.selected_model}</strong></div><div className="card"><small>Horizon</small><strong>{r.forecast.length} days</strong></div><div className="card"><small>MAPE</small><strong>{Number(r.metrics.mape).toFixed(2)}%</strong></div></div><div className="panel"><h2>Forecast Table</h2><Table headers={["Date","Forecast","Lower 95%","Upper 95%"]} rows={r.forecast.map(x=>[x.date,Number(x.value).toFixed(2),x.lower_95==null?"—":Number(x.lower_95).toFixed(2),x.upper_95==null?"—":Number(x.upper_95).toFixed(2)])}/></div></>}</Layout>;
}

function ModelLab({ type }) {
  const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[h,setH]=useState(30),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);
  async function run(){setLoading(true);setError("");try{setR(await api(`/forecast/${type.toLowerCase()}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:Number(pid),horizon:Number(h),models:[type]})}))}catch(e){setError(e.message)}finally{setLoading(false)}}
  return <Layout><Header title={`${type} Lab`} sub={`${type} forecasting engine`}/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><select value={h} onChange={e=>setH(e.target.value)}><option>7</option><option>30</option><option>60</option><option>90</option></select><button onClick={run} disabled={!pid||loading}>{loading?"Training…":`Run ${type}`}</button></div>{error&&<div className="error">{error}</div>}{r&&<><div className="cards"><div className="card"><small>MAE</small><strong>{Number(r.metrics.mae).toFixed(2)}</strong></div><div className="card"><small>RMSE</small><strong>{Number(r.metrics.rmse).toFixed(2)}</strong></div><div className="card"><small>MAPE</small><strong>{Number(r.metrics.mape).toFixed(2)}%</strong></div></div><div className="panel"><h2>{type} Forecast</h2><Table headers={["Date","Forecast"]} rows={r.forecast.map(x=>[x.date,Number(x.value).toFixed(2)])}/></div></>}</Layout>;
}

function Evaluation(){const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);async function run(){setLoading(true);setError("");try{setR(await api("/evaluation/compare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:Number(pid),horizon:30,models:["ARIMA","LSTM"]})}))}catch(e){setError(e.message)}finally{setLoading(false)}}return <Layout><Header title="Model Evaluation" sub="ARIMA vs LSTM on chronological validation data"/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><button onClick={run} disabled={!pid||loading}>{loading?"Evaluating…":"Compare Models"}</button></div>{error&&<div className="error">{error}</div>}{r&&<><div className="cards"><div className="card"><small>Winner</small><strong>{r.winner}</strong></div><div className="card"><small>Primary Metric</small><strong>{r.primary_metric}</strong></div></div><div className="panel"><Table headers={["Rank","Model","MAPE","RMSE","MAE"]} rows={r.models.map(x=>[x.rank,x.model,`${Number(x.mape).toFixed(2)}%`,Number(x.rmse).toFixed(2),Number(x.mae).toFixed(2)])}/></div></>}</Layout>}

function Seasonality(){const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[s,setS]=useState(null),[a,setA]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);async function run(){setLoading(true);setError("");try{const [x,y]=await Promise.all([api(`/seasonality?product_id=${pid}`),api(`/anomalies?product_id=${pid}`)]);setS(x);setA(y)}catch(e){setError(e.message)}finally{setLoading(false)}}return <Layout><Header title="Seasonality & Anomalies" sub="Recurring demand patterns and unusual sales behavior"/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><button onClick={run} disabled={!pid||loading}>{loading?"Analyzing…":"Analyze"}</button></div>{error&&<div className="error">{error}</div>}{s&&a&&<><div className="cards"><div className="card"><small>Baseline</small><strong>{s.baseline_daily_demand}</strong></div><div className="card"><small>Strongest Day</small><strong>{s.strongest_weekday.label}</strong></div><div className="card"><small>Anomalies</small><strong>{a.anomaly_count}</strong></div></div><div className="comparison"><div className="panel"><h2>Weekly Pattern</h2><Table headers={["Day","Average","Index"]} rows={s.weekday_pattern.map(x=>[x.label,x.average,x.index])}/></div><div className="panel"><h2>Anomalies</h2><Table headers={["Date","Type","Actual","Z-score"]} rows={a.anomalies.map(x=>[x.date,x.type,x.actual,x.z_score])}/></div></div></>}</Layout>}

function RestockCenter(){const {data:d,error,loading}=useLoad("/restock/center",[]);if(loading)return <Layout><div className="loading">Calculating replenishment recommendations…</div></Layout>;return <Layout><Header title="Restock Center" sub="Prioritized replenishment recommendations"/>{error&&<div className="error">{error}</div>}<div className="cards">{[["Urgent",d?.urgent],["High",d?.high],["Normal",d?.normal],["Products to Order",d?.products_needing_order],["Recommended Units",d?.recommended_units]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong></div>)}</div><div className="panel"><Table headers={["Priority","Product","Stock","Daily Demand","Reorder Point","Recommended Order"]} rows={(d?.items||[]).map(x=>[<Badge x={x.priority}/>,x.product,x.current_stock,x.planning_daily_demand,x.reorder_point,x.recommended_order])}/></div></Layout>}

function Inventory(){
  const {data:d,error,loading}=useLoad("/inventory",[]);
  if(loading)return <Layout><div className="loading">Building inventory intelligence…</div></Layout>;
  return <Layout><Header title="Inventory Intelligence" sub="Stock health, demand velocity and replenishment risk"/>
    {error&&<div className="error">{error}</div>}
    <div className="cards">{[["Products",d?.total_products],["Stock Units",d?.total_stock_units],["Critical",d?.critical],["Attention",d?.attention],["Health Score",d?.health_score==null?"—":`${d.health_score}%`]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong></div>)}</div>
    <div className="panel"><div className="panel-title"><div><h2>Inventory Risk Map</h2><p>Prioritized by current stock, demand velocity and reorder point.</p></div><Link className="outline" to="/restock-center">Open Restock Center →</Link></div>
      <Table headers={["Risk","Product","Stock","Daily Demand","Reorder Point","Days Cover"]} rows={(d?.items||[]).map(x=>[<Badge x={x.inventory_risk}/>,x.product,x.current_stock,x.average_daily_demand,x.reorder_point,x.days_of_cover??"—"])}/>
    </div>
  </Layout>
}

function Scenarios(){const [products,setProducts]=useState([]),[pid,setPid]=useState(""),[demand,setDemand]=useState(0),[lead,setLead]=useState(0),[safety,setSafety]=useState(0),[h,setH]=useState(30),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);useEffect(()=>{api("/products").then(x=>{setProducts(x);if(x[0])setPid(String(x[0].id))}).catch(e=>setError(e.message))},[]);async function run(){setLoading(true);setError("");try{const x=await api("/scenarios",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:Number(pid),horizon:Number(h),demand_change_pct:Number(demand),lead_time_change_days:Number(lead),safety_stock_change_pct:Number(safety)})});setR(x)}catch(e){setError(e.message)}finally{setLoading(false)}}return <Layout><Header title="Scenario Planner" sub="What-if demand, lead-time and safety-stock analysis"/><div className="panel controls"><select value={pid} onChange={e=>setPid(e.target.value)}>{products.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><select value={h} onChange={e=>setH(e.target.value)}><option>7</option><option>30</option><option>60</option><option>90</option></select><input type="number" value={demand} onChange={e=>setDemand(e.target.value)} placeholder="Demand %"/><input type="number" value={lead} onChange={e=>setLead(e.target.value)} placeholder="Lead days"/><input type="number" value={safety} onChange={e=>setSafety(e.target.value)} placeholder="Safety %"/><button onClick={run} disabled={!pid||loading}>{loading?"Calculating…":"Run Scenario"}</button></div>{error&&<div className="error">{error}</div>}{r&&<div className="panel"><div className="cards"><div className="card"><small>Scenario Demand/Day</small><strong>{r.scenario_daily_demand}</strong></div><div className="card"><small>Reorder Point</small><strong>{r.reorder_point}</strong></div><div className="card"><small>Recommended Order</small><strong>{r.recommended_order}</strong></div><div className="card"><small>Risk</small><strong>{r.risk}</strong></div></div><Table headers={["Metric","Value"]} rows={[["Base demand/day",r.base_daily_demand],["Scenario demand/day",r.scenario_daily_demand],["Lead time",`${r.scenario_lead_time_days} days`],["Safety stock",r.scenario_safety_stock],["Target stock",r.target_stock],["Days cover",r.days_of_cover ?? "—"]]}/></div>}</Layout>}

function Alerts(){const {data:d,error,loading}=useLoad("/alerts",[]);if(loading)return <Layout><div className="loading">Loading action center…</div></Layout>;return <Layout><Header title="Executive Action Center" sub="Prioritized operational alerts"/>{error&&<div className="error">{error}</div>}<div className="cards">{[["Critical",d?.critical],["High",d?.high],["Medium",d?.medium],["Total",d?.total]].map(([a,b])=><div className="card" key={a}><small>{a}</small><strong>{b??"—"}</strong></div>)}</div><div className="panel"><Table headers={["Severity","Type","Alert","SKU"]} rows={(d?.alerts||[]).map(a=>[<Badge x={a.severity}/>,a.type,<><b>{a.title}</b><br/><span className="muted">{a.message}</span></>,a.sku])}/></div></Layout>}

function MiniLineChart({series=[]}){const w=900,h=260,p=34,vals=series.map(x=>Number(x.units)||0),max=Math.max(...vals,1),min=Math.min(...vals,0);const pts=series.map((x,i)=>[p+i*(w-2*p)/Math.max(series.length-1,1),h-p-((Number(x.units)-min)/Math.max(max-min,1))*(h-2*p)]);const d=pts.map((x,i)=>(i?'L':'M')+x[0].toFixed(1)+','+x[1].toFixed(1)).join(' ');return <svg className="report-chart" viewBox={`0 0 ${w} ${h}`}><defs><linearGradient id="lineGlow" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".28"/><stop offset="1" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs><path d={`${d} L ${w-p},${h-p} L ${p},${h-p} Z`} fill="url(#lineGlow)"/><path d={d} fill="none" stroke="currentColor" strokeWidth="3"/><line x1={p} y1={h-p} x2={w-p} y2={h-p} stroke="currentColor" opacity=".14"/>{pts.filter((_,i)=>i===0||i===pts.length-1).map(([x,y],i)=><circle key={i} cx={x} cy={y} r="4" fill="currentColor"/> )}</svg>}
function MiniBarChart({series=[]}){const max=Math.max(...series.map(x=>Number(x.units)||0),1);return <div className="report-bars">{series.map((x,i)=><div className="report-bar-col" key={x.label}><div className="report-bar" style={{height:`${Math.max(3,(Number(x.units)||0)/max*100)}%`}} title={`${x.label}: ${x.units}`}/><span>{series.length>16?(i%5===0?x.label:""):x.label}</span></div>)}</div>}
function Reports(){const [period,setPeriod]=useState("daily"),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);async function load(p=period){setLoading(true);setError("");try{setR(await api(`/reports/periodic?period=${p}`))}catch(e){setError(e.message)}finally{setLoading(false)}}useEffect(()=>{load(period)},[period]);return <Layout><Header title="Reports & Analytics" sub="Daily, weekly, monthly and yearly retail intelligence"/><div className="report-tabs">{[["daily","Daily"],["weekly","Weekly"],["monthly","Monthly"],["yearly","Yearly"]].map(([v,l])=><button key={v} className={period===v?"active":""} onClick={()=>setPeriod(v)}>{l} Report</button>)}</div>{error&&<div className="error">{error}</div>}{loading&&!r?<div className="loading">Building {period} report…</div>:r&&<><div className="cards report-kpis">{[["Total Units",r.kpis.total_units,"Σ"],["Average Period Units",r.kpis.average_units,"AVG"],["Peak Units",r.kpis.peak_units,"PEAK"],["Growth",r.kpis.growth_pct==null?"—":`${r.kpis.growth_pct}%`,"Δ"],["Records",r.kpis.records,"ROWS"]].map(([a,b,c])=><div className="kpi-card" key={a}><span>{c}</span><small>{a}</small><strong>{b}</strong></div>)}</div><div className="report-grid"><div className="panel chart-panel"><div className="panel-title"><div><h2>{period[0].toUpperCase()+period.slice(1)} Demand Trend</h2><p>Recorded sales units by reporting period</p></div><button className="secondary" onClick={()=>load()}>↻ Refresh</button></div><MiniLineChart series={r.series}/><MiniBarChart series={r.series}/></div><div className="panel"><div className="panel-title"><div><h2>Top Products</h2><p>Highest recorded unit volume</p></div></div><Table headers={["Product","Units"]} rows={(r.top_products||[]).map(x=>[x.product,x.units])}/></div></div><div className="report-footer-grid"><div className="insight-card"><span>✦</span><div><b>AI report insight</b><p>{r.kpis.growth_pct==null?"More history is needed to calculate period-over-period growth.":r.kpis.growth_pct>=0?`Demand is trending up ${r.kpis.growth_pct}% versus the previous period.`:`Demand is trending down ${Math.abs(r.kpis.growth_pct)}% versus the previous period.`}</p></div></div><Link className="report-action" to="/copilot">Ask Copilot about this report →</Link></div></>}</Layout>}

function Copilot(){const [q,setQ]=useState("Which products should I restock?"),[r,setR]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);async function ask(){setLoading(true);setError("");try{setR(await api("/copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})}))}catch(e){setError(e.message)}finally{setLoading(false)}}const prompts=["Which products should I restock?","What is my demand trend?","Which products are at risk?","How accurate are my forecasts?","Show me top selling products."];return <Layout><Header title="Retail Copilot" sub="Grounded AI decision support for your store"/><div className="copilot-hero"><div className="ai-core"><div className="ai-orbit orbit-1"/><div className="ai-orbit orbit-2"/><div className="ai-core-face">✦</div></div><div><span className="eyebrow">RETAIL INTELLIGENCE AI</span><h2>Ask your store anything.</h2><p>Copilot answers from your uploaded sales, products, inventory and stored forecasting data.</p></div></div><div className="suggestions large">{prompts.map(x=><button className="chip" key={x} onClick={()=>setQ(x)}>{x}</button>)}</div><div className="copilot-composer"><textarea value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask()}}} placeholder="Ask about demand, forecasts, inventory, risk or restocking…"/><button onClick={ask} disabled={loading}><span>✦</span>{loading?"Analyzing…":"Ask Copilot"}</button></div>{error&&<div className="error">{error}</div>}{r&&<div className="panel answer"><div className="answer-label">GROUNDED RESPONSE</div><h2>{r.answer}</h2><div className="source-row">Sources: {(r.sources||[]).join(" · ")}</div>{Array.isArray(r.data)?<Table headers={Object.keys(r.data[0]||{}).slice(0,5).map(x=>x.replaceAll("_"," "))} rows={r.data.slice(0,8).map(row=>Object.values(row).slice(0,5))}/>:<pre>{JSON.stringify(r.data,null,2)}</pre>}<div className="insight-card"><span>→</span><div><b>Recommended next step</b><p>{r.action}</p></div></div></div>}</Layout>}

function Settings(){
  const [d,setD]=useState(null);
  const [error,setError]=useState("");
  const [form,setForm]=useState({email:"",password:"",role:"STAFF"});
  const [created,setCreated]=useState("");
  const [loading,setLoading]=useState(true);

  async function load(){
    setLoading(true); setError("");
    try{
      const x=await api("/settings/overview");
      setD(x);
    }catch(e){
      setError(e.message||"Unable to load settings.");
    }finally{setLoading(false);}
  }

  useEffect(()=>{load()},[]);

  async function create(){
    setCreated("");
    if(!form.email||!form.password){setCreated("Email and password are required.");return;}
    try{
      await api("/users",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(form)
      });
      setCreated("User created successfully.");
      setForm({email:"",password:"",role:"STAFF"});
      await load();
    }catch(e){setCreated(e.message||"Unable to create user.");}
  }

  if(loading)return <Layout><Header title="Settings & Access" sub="Owner administration"/><div className="loading">Loading owner settings…</div></Layout>;
  if(error)return <Layout><Header title="Settings & Access" sub="Owner administration"/><div className="error">Settings API error: {error}<br/><span className="muted">Check the backend terminal for the exact exception.</span></div></Layout>;

  const tenant=d?.tenant||{name:"RetailPulse AI"};
  const stores=Array.isArray(d?.stores)?d.stores:[];
  const users=Array.isArray(d?.users)?d.users:[];
  const roles=Array.isArray(d?.roles)?d.roles:["OWNER","MANAGER","STAFF","ANALYST","CUSTOMER"];
  const matrix=d?.permission_matrix||{};

  return <Layout>
    <Header title="Settings & Access" sub="Owner-only workspace administration and role permissions"/>
    <div className="settings-hero">
      <div><span className="eyebrow">OWNER CONTROL CENTER</span><h2>{tenant.name}</h2><p>Manage users, roles, stores and feature access.</p></div>
      <div className="security-badge">🔐 OWNER ACCESS</div>
    </div>

    <div className="settings-grid">
      <div className="panel">
        <h2>Workspace</h2>
        <div className="metric-row"><span>Tenant</span><b>{tenant.name}</b></div>
        <div className="metric-row"><span>Stores</span><b>{stores.length}</b></div>
        <div className="metric-row"><span>Users</span><b>{users.length}</b></div>
        <div className="metric-row"><span>Roles</span><b>{roles.join(" · ")}</b></div>
      </div>

      <div className="panel">
        <h2>Create User</h2>
        <div className="form-grid">
          <input placeholder="Email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
          <input type="password" placeholder="Temporary password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>
          <select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>
            {roles.map(r=><option key={r}>{r}</option>)}
          </select>
        </div>
        <button onClick={create}>Create User</button>
        {created&&<p className={created.includes("successfully")?"success":"error"}>{created}</p>}
      </div>
    </div>

    <div className="panel">
      <h2>User Directory</h2>
      <Table headers={["Email","Role","Store","Status"]} rows={users.map(u=>[
        u.email,<Badge x={u.role}/>,stores.find(s=>s.id===u.store_id)?.name||"All stores",
        u.active?"Active":"Disabled"
      ])}/>
    </div>

    <div className="panel">
      <h2>Role Access Matrix</h2>
      <div className="permission-grid">
        {Object.entries(matrix).map(([role,perms])=>
          <div className="permission-card" key={role}>
            <div className="permission-title"><Badge x={role}/><b>{role}</b></div>
            <div className="permission-list">{(perms||[]).map(p=><span key={p}>✓ {p.replaceAll("_"," ")}</span>)}</div>
          </div>
        )}
      </div>
    </div>
  </Layout>
}

class AppErrorBoundary extends React.Component{
  constructor(props){super(props);this.state={error:null}}
  static getDerivedStateFromError(error){return {error}}
  componentDidCatch(error,info){console.error("RetailPulse UI error",error,info)}
  render(){
    if(this.state.error){
      return <div style={{padding:"40px",fontFamily:"system-ui",background:"#070b16",color:"#fff",minHeight:"100vh"}}>
        <h1>RetailPulse AI</h1>
        <h2>UI error</h2>
        <pre style={{whiteSpace:"pre-wrap",color:"#ff9b9b"}}>{String(this.state.error?.stack||this.state.error)}</pre>
        <button onClick={()=>location.reload()}>Reload application</button>
      </div>
    }
    return this.props.children
  }
}

function Protected({ children }) { return <RequireAuth>{children}</RequireAuth>; }
function App(){return <Routes><Route path="/login" element={<Login/>}/><Route path="/" element={<Protected><Dashboard/></Protected>}/><Route path="/products" element={<Protected><Products/></Protected>}/><Route path="/data" element={<Protected><RoleGate permission="data_upload"><Data/></RoleGate></Protected>}/><Route path="/studio" element={<Protected><RoleGate permission="forecasts"><ForecastStudio/></RoleGate></Protected>}/><Route path="/forecast" element={<Navigate to="/studio" replace/>}/><Route path="/arima" element={<Protected><RoleGate permission="arima"><ModelLab type="ARIMA"/></RoleGate></Protected>}/><Route path="/lstm" element={<Protected><RoleGate permission="lstm"><ModelLab type="LSTM"/></RoleGate></Protected>}/><Route path="/evaluation" element={<Protected><RoleGate permission="model_center"><Evaluation/></RoleGate></Protected>}/><Route path="/seasonality" element={<Protected><RoleGate permission="seasonality"><Seasonality/></RoleGate></Protected>}/><Route path="/inventory" element={<Protected><RoleGate permission="inventory"><Inventory/></RoleGate></Protected>}/><Route path="/restock-center" element={<Protected><RoleGate permission="restock"><RestockCenter/></RoleGate></Protected>}/><Route path="/scenarios" element={<Protected><RoleGate permission="scenarios"><Scenarios/></RoleGate></Protected>}/><Route path="/alerts" element={<Protected><RoleGate permission="alerts"><Alerts/></RoleGate></Protected>}/><Route path="/reports" element={<Protected><RoleGate permission="reports"><Reports/></RoleGate></Protected>}/><Route path="/copilot" element={<Protected><RoleGate permission="copilot"><Copilot/></RoleGate></Protected>}/><Route path="/settings" element={<Protected><RoleGate permission="settings"><Settings/></RoleGate></Protected>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}

createRoot(document.getElementById("root")).render(<AppErrorBoundary><BrowserRouter><App/></BrowserRouter></AppErrorBoundary>);
