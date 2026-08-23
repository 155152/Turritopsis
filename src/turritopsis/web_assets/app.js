const state = { project: null, route: "map", searchMode: "semantic", searchQuery: "", draft: null };
const view = document.querySelector("#view");
const modal = document.querySelector("#modal");
const modalBody = document.querySelector("#modal-body");
const platform = navigator.userAgentData?.platform || navigator.platform || "";
document.querySelector("#search-shortcut").textContent = /mac/i.test(platform) ? "⌘ K" : "Ctrl K";

const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const qs = value => encodeURIComponent(value);
const icon = (name, className = "") => `<svg class="ui-icon ${className}" aria-hidden="true"><use href="#${name}"></use></svg>`;
async function loadIcons() {
  const response = await fetch("/assets/icons.svg");
  if (!response.ok) throw new Error("Unable to load the icon system.");
  document.body.insertAdjacentHTML("afterbegin", await response.text());
}
const fmtTime = value => {
  if (!value) return "Never";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  const seconds = Math.max(0, (Date.now() - date.getTime()) / 1000);
  if (seconds < 90) return "just now"; if (seconds < 3600) return `${Math.floor(seconds/60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds/3600)}h ago`; if (seconds < 172800) return "yesterday";
  return date.toLocaleDateString(undefined, {year:"numeric", month:"short", day:"numeric"});
};
const statusIcon = stage => icon(stage.stale_reasons?.length ? "scan-eye" : stage.authority ? "star" : stage.status === "historical" ? "landmark" : stage.status === "generated" ? "gauge" : stage.status === "unresolved" ? "user-round-search" : "layers");
const toast = message => { const node = document.querySelector("#toast"); node.textContent = message; node.classList.add("show"); setTimeout(() => node.classList.remove("show"), 2400); };

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type":"application/json"}, ...options});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok && response.status !== 409) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

function labels(stage) {
  const out = [];
  if (stage.stale_reasons?.length) out.push(`<span class="label stale">possibly stale</span>`);
  out.push(`<span class="label ${esc(stage.status)}">${esc(stage.status)}</span>`);
  if (stage.authority) out.push(`<span class="label authority">authority</span>`);
  return out.join("");
}

async function loadProject() {
  state.project = await api("/api/project");
  document.querySelector("#revision-label").textContent = `REV ${state.project.revision}`;
  const badge = document.querySelector("#proposal-badge");
  badge.textContent = state.project.counts.proposals; badge.hidden = !state.project.counts.proposals;
}

function route(name, param = "") {
  state.route = name;
  document.querySelectorAll(".nav-item").forEach(node => node.classList.toggle("active", node.dataset.route === name));
  if (name === "map") return renderMap();
  if (name === "authority") return renderAuthority();
  if (name === "history") return renderHistory();
  if (name === "proposals") return renderProposals();
  if (name === "stage") return renderStage(param);
  if (name === "search") return renderSearch(state.searchQuery);
}

function renderMap() {
  const p = state.project;
  view.innerHTML = `
    <section class="map-header">
      <div><p class="eyebrow">Project map · ${esc(p.revision)}</p><h1 class="page-title">${esc(p.title)}</h1><p class="page-subtitle">${esc(p.subtitle || "A shared address for what this project has learned.")}</p></div>
      <div class="vitals"><div class="vital"><b>${p.currents.length}</b><span>Currents</span></div><div class="vital"><b>${p.counts.stale}</b><span>Possibly stale</span></div><div class="vital"><b>${p.counts.proposals}</b><span>To review</span></div></div>
    </section>
    ${p.handoff ? `<button class="handoff-beacon" data-stage="${esc(p.handoff.stage_id)}"><span><small>CURRENT HANDOFF · ${esc(p.handoff.current)}</small><strong>${esc(p.handoff.title)}</strong><p>${esc(p.handoff.summary || "Open the current handoff surface.")}</p></span>${icon("chart-network", "handoff-icon")}</button>` : ""}
    <section class="current-map">${p.currents.map(current => `
      <article class="current-section">
        <header class="current-heading"><small>CURRENT / ${esc(current.id)}</small><h2>${esc(current.name)}</h2><p>${esc(current.blurb || "No description yet.")}</p></header>
        <div class="stage-list">${current.stages.length ? current.stages.map(stage => `
          <button class="stage-row ${stage.authority ? "authority" : ""} ${stage.stale_reasons?.length ? "stale" : ""}" data-stage="${esc(stage.stage_id)}">
            <span class="stage-symbol" aria-hidden="true">${statusIcon(stage)}</span>
            <span class="stage-name"><b>${esc(stage.title)}</b><code>${esc(stage.stage_id)}</code></span>
            <span class="stage-summary">${esc(stage.summary || "Empty Stage — address reserved.")}</span>
            <span class="labels">${labels(stage)}</span>
          </button>`).join("") : `<p class="empty-state">No Stage addresses have been added to this Current.</p>`}</div>
      </article>`).join("")}</section>`;
}

function markdown(source) {
  const codeBlocks = [];
  let text = String(source || "").replace(/```([^\n]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const token = `@@CODE${codeBlocks.length}@@`; codeBlocks.push(`<pre><code data-lang="${esc(lang)}">${esc(code.trimEnd())}</code></pre>`); return token;
  });
  text = esc(text);
  text = text.replace(/^###### (.+)$/gm,"<h6>$1</h6>").replace(/^##### (.+)$/gm,"<h5>$1</h5>").replace(/^#### (.+)$/gm,"<h4>$1</h4>").replace(/^### (.+)$/gm,"<h3>$1</h3>").replace(/^## (.+)$/gm,"<h2>$1</h2>").replace(/^# (.+)$/gm,"<h1>$1</h1>");
  text = text.replace(/^&gt; (.+)$/gm,"<blockquote>$1</blockquote>");
  text = text.replace(/^[-*] (.+)$/gm,"<li>$1</li>").replace(/(?:<li>[\s\S]*?<\/li>\n?)+/g, block => `<ul>${block}</ul>`);
  text = text.replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>").replace(/\*([^*]+)\*/g,"<em>$1</em>");
  text = text.replace(/\b([a-z0-9_-]+\.[a-z0-9_.-]+)\b/gi, `<span class="stage-ref" data-stage="$1">$1</span>`);
  text = text.split(/\n{2,}/).map(block => /^<(h\d|ul|blockquote|pre)/.test(block) ? block : `<p>${block.replace(/\n/g,"<br>")}</p>`).join("\n");
  codeBlocks.forEach((block, index) => { text = text.replace(`<p>@@CODE${index}@@</p>`, block).replace(`@@CODE${index}@@`, block); });
  return text;
}

async function renderStage(id) {
  view.innerHTML = `<div class="loading">Reading complete Stage</div>`;
  try {
    const stage = await api(`/api/stages/${qs(id)}`);
    const generated = stage.metadata.status === "generated";
    view.innerHTML = `
      <header class="section-head"><div><p class="eyebrow">${esc(stage.current.name)} / ${esc(stage.current.id)}</p><h1 class="page-title">${esc(stage.title)}</h1><div class="stage-meta">${labels({...stage, status:stage.metadata.status, authority:stage.metadata.authority})}</div><p class="meta-line">${esc(stage.stage_id)} · REV ${esc(stage.revision)} · VERIFIED ${esc(stage.metadata.verified || "not recorded")} ${stage.last_change ? `· LAST CHANGED BY ${esc(stage.last_change.actor)}` : ""}</p></div><button class="back icon-button" data-route="map">${icon("map")}<span>Project map</span></button></header>
      ${stage.stale_reasons.length ? `<div class="notice"><b>POSSIBLY STALE</b><br>Relevant project evidence changed after this Stage was verified. Canonical content has not been modified.</div>` : ""}
      ${generated ? `<div class="notice"><b>AUTO-GENERATED</b><br>This Stage is maintained by a deterministic scanner. Manual edits may be overwritten.</div>` : ""}
      <div class="stage-layout"><article class="reader">${markdown(stage.body || "_This Stage is empty._")}</article><aside class="side-index"><h3>In this Current</h3>${stage.siblings.map(item => `<button class="side-stage ${item.stage_id === stage.stage_id ? "active" : ""}" data-stage="${esc(item.stage_id)}">${statusIcon(item)}<span>${esc(item.title)}</span></button>`).join("")}<div class="side-actions"><button class="primary" data-edit="${esc(stage.stage_id)}" ${generated ? "disabled title=\"Generated Stage\"" : ""}>Edit Stage</button>${generated ? `<button class="secondary" data-edit-generated="${esc(stage.stage_id)}">Edit anyway…</button>` : ""}</div></aside></div>`;
    view.querySelectorAll("[data-edit]").forEach(node => node.addEventListener("click", () => openEditor(stage)));
    view.querySelectorAll("[data-edit-generated]").forEach(node => node.addEventListener("click", () => confirmGeneratedEdit(stage)));
  } catch (error) { renderError(error); }
}

const META = {purpose:["Purpose","用途"], search_hints:["Search hints","适合检索"], summary:["Summary","一句话概括"], status:["Status","当前性"], authority:["Authority","权威范围"], verified:["Verified","最后核验"]};
function replaceMeta(body, values) {
  let text = body;
  Object.entries(META).forEach(([key, names]) => {
    const pattern = new RegExp(`^(${names.join("|")})\\s*[:：].*$`, "im");
    const value = values[key]?.trim();
    if (pattern.test(text)) text = value ? text.replace(pattern, `${names[0]}: ${value}`) : text.replace(pattern, "");
    else if (value) {
      const heading = text.match(/^# .+$/m); const position = heading ? heading.index + heading[0].length : 0;
      text = text.slice(0, position) + `\n${names[0]}: ${value}` + text.slice(position);
    }
  });
  return text.replace(/\n{3,}/g,"\n\n").trim() + "\n";
}

function openEditor(stage) {
  state.draft = {stage, body:stage.body};
  view.innerHTML = `<header class="section-head"><div><p class="eyebrow">Edit Stage · optimistic revision lock</p><h1 class="page-title">${esc(stage.title)}</h1><p class="meta-line">Editing REV ${esc(stage.revision)}. A concurrent Agent write cannot be overwritten silently.</p></div><button class="back" data-stage="${esc(stage.stage_id)}">Cancel</button></header>
    <div class="editor-shell"><section class="editor-pane"><div class="field-grid">
      ${["purpose","search_hints","summary","authority","verified"].map(key => `<div class="field ${["search_hints","summary"].includes(key)?"wide":""}"><label>${META[key][0]}</label><input data-meta="${key}" value="${esc(stage.metadata[key])}"></div>`).join("")}
      <div class="field"><label>Status</label><select data-meta="status">${["current","historical","generated","stale","unresolved"].map(value=>`<option ${value===stage.metadata.status?"selected":""}>${value}</option>`).join("")}</select></div>
      </div><div class="field"><label>Advanced Markdown</label><textarea id="markdown-editor" class="markdown-editor" spellcheck="false">${esc(stage.body)}</textarea></div><div class="editor-actions"><button class="secondary" data-stage="${esc(stage.stage_id)}">Discard</button><button class="primary" id="save-stage">Save with revision check</button></div></section><aside class="preview-pane"><p class="eyebrow">Live preview</p><article id="live-preview" class="reader">${markdown(stage.body)}</article></aside></div>`;
  const editor = document.querySelector("#markdown-editor");
  const refresh = () => { const values = Object.fromEntries([...view.querySelectorAll("[data-meta]")].map(node => [node.dataset.meta,node.value])); state.draft.body = replaceMeta(editor.value, values); document.querySelector("#live-preview").innerHTML = markdown(state.draft.body); };
  editor.addEventListener("input", refresh); view.querySelectorAll("[data-meta]").forEach(node => node.addEventListener("input", refresh));
  document.querySelector("#save-stage").addEventListener("click", async () => { refresh(); await saveStage(stage, state.draft.body); });
}

async function saveStage(stage, body) {
  try {
    const result = await api(`/api/stages/${qs(stage.stage_id)}`, {method:"PUT", body:JSON.stringify({body, expected_revision:stage.revision, actor:"human-web-ui"})});
    if (result.conflict) return showConflict(stage, body, result.current_stage);
    toast("Canonical Stage updated"); await loadProject(); route("stage", stage.stage_id);
  } catch (error) { toast(error.message); }
}

function confirmGeneratedEdit(stage) {
  modalBody.innerHTML = `<div class="modal-inner"><p class="eyebrow">Generated knowledge</p><h2>This Stage may be overwritten</h2><p>Its deterministic scanner remains authoritative for the generated facts. Continue only if you understand the next refresh can replace this edit.</p><div class="modal-actions"><button class="secondary" data-close>Cancel</button><button class="danger" id="continue-generated">Edit anyway</button></div></div>`;
  modal.showModal(); document.querySelector("#continue-generated").onclick = () => { modal.close(); openEditor(stage); };
}

function showConflict(stage, draft, current) {
  modalBody.innerHTML = `<div class="modal-inner"><p class="eyebrow">Revision conflict</p><h2>This Stage changed while you were editing.</h2><p>Your revision: ${esc(stage.revision)} · Current revision: ${esc(current.revision)}. Review both versions and merge deliberately.</p><div class="conflict-grid"><section><p class="eyebrow">Your draft</p><pre>${esc(draft)}</pre></section><section><p class="eyebrow">Current canonical</p><pre>${esc(current.body)}</pre></section></div><div class="field wide"><label>Manual merge draft</label><textarea id="merge-draft" class="proposal-json">${esc(draft)}</textarea></div><div class="modal-actions"><button class="secondary" id="use-current">Discard mine</button><button class="secondary" data-close>Keep editing</button><button class="primary" id="save-merge">Save merge against current revision</button></div></div>`;
  modal.showModal(); document.querySelector("#use-current").onclick = () => { modal.close(); route("stage", stage.stage_id); };
  document.querySelector("#save-merge").onclick = async () => { modal.close(); await saveStage(current, document.querySelector("#merge-draft").value); };
}

async function renderSearch(query) {
  view.innerHTML = `<div class="loading">Routing across knowledge</div>`;
  try {
    const result = await api(`/api/search?q=${qs(query)}&match=${state.searchMode}&limit=20`);
    view.innerHTML = `<header class="section-head"><div><p class="eyebrow">Global search · shared with MCP</p><h1 class="page-title">${esc(query)}</h1><p class="page-subtitle">${result.count} ${result.count===1?"Stage":"Stages"} found. Ranked search routes by authored fields; exact search preserves line evidence.</p><div class="search-controls"><div class="segmented"><button data-mode="semantic" class="${state.searchMode==="semantic"?"active":""}">Ranked</button><button data-mode="exact" class="${state.searchMode==="exact"?"active":""}">Exact</button></div></div></div><button class="back icon-button" data-route="map">${icon("map")}<span>Project map</span></button></header><section>${result.results.map(item => state.searchMode === "semantic" ? `
      <article class="result"><button data-stage="${esc(item.stage_id)}"><code>${esc(item.stage_id)}</code><h3>${esc(item.title)}</h3><span class="label ${esc(item.status)}">${esc(item.status)}</span></button><div class="result-copy"><p>${esc(item.snippet)}</p><span class="matched">Matched: ${item.matched.map(hit=>esc(hit.field)).join(" · ")} ${item.authority?` · Authority: ${esc(item.authority)}`:""}</span></div></article>` : `
      <article class="result"><button data-stage="${esc(item.stage_id)}"><code>${esc(item.stage_id)}</code><h3>${esc(item.title)}</h3><span class="label ${esc(item.status)}">${esc(item.status)}</span></button><div class="result-copy"><span class="matched">${esc(item.heading)} · LINE ${item.line} ${item.authority?` · Authority: ${esc(item.authority)}`:""}</span><pre class="exact-context">${item.context.map(line => `${line.match?"<mark>":""}${esc(String(line.line).padStart(3," "))}  ${esc(line.text)}${line.match?"</mark>":""}`).join("\n")}</pre></div></article>`).join("") || `<p class="empty-state">No match. Try another term or switch search mode.</p>`}</section>`;
    view.querySelectorAll("[data-mode]").forEach(node => node.onclick = () => { state.searchMode=node.dataset.mode; renderSearch(query); });
  } catch (error) { renderError(error); }
}

function renderAuthority() {
  const rows = state.project.authority;
  view.innerHTML = `<header class="section-head"><div><p class="eyebrow">Where is truth?</p><h1 class="page-title">Authority index</h1><p class="page-subtitle">When several Stages mention the same subject, start with the Stage assigned to decide that class of question.</p></div></header><section class="authority-grid">${rows.map(row=>`<article class="authority-row"><div><strong>${esc(row.authority)}</strong><small>${esc(row.current)} · ${esc(row.title)}</small></div><button class="icon-button" data-stage="${esc(row.stage_id)}"><span>${esc(row.stage_id)}</span>${icon("locate-fixed")}</button></article>`).join("") || `<p class="empty-state">No Authority metadata has been assigned yet.</p>`}</section>`;
}

async function renderHistory() {
  view.innerHTML = `<div class="loading">Reading knowledge history</div>`;
  try { const data = await api("/api/history"); view.innerHTML = `<header class="section-head"><div><p class="eyebrow">Canonical write log</p><h1 class="page-title">History</h1><p class="page-subtitle">Who changed which region of project understanding, and when. Git remains the long-term diff system.</p></div></header><section>${data.entries.map(row=>`<article class="list-row"><time>${esc(fmtTime(row.timestamp))}</time><div><h3>${esc(row.stage_id)}</h3><p>${esc(row.actor)} · ${esc(row.mode)} · ${esc(row.before_revision)} → ${esc(row.after_revision)}</p></div><button class="icon-button" data-history="${row.index}"><span>Inspect</span>${icon("scan-eye")}</button></article>`).join("") || `<p class="empty-state">No canonical Stage updates have been recorded.</p>`}</section>`; view.querySelectorAll("[data-history]").forEach(node=>node.onclick=()=>openHistory(node.dataset.history)); } catch(error){renderError(error);}
}

async function openHistory(index) {
  const data = await api(`/api/history/${index}`); const row=data.entry;
  modalBody.innerHTML=`<div class="modal-inner"><p class="eyebrow">${esc(row.timestamp)} · ${esc(row.actor)}</p><h2>${esc(row.stage_id)}</h2><p>Revision ${esc(row.before_revision)} → ${esc(row.after_revision)} · mode ${esc(row.mode)}</p><div class="conflict-grid"><section><p class="eyebrow">Before</p><pre>${esc(data.before_body ?? "Body unavailable; use Git for the durable diff.")}</pre></section><section><p class="eyebrow">After</p><pre>${esc(data.after_body ?? "A later update has replaced this revision; use Git for the durable diff.")}</pre></section></div><div class="modal-actions"><button class="primary" data-close>Close</button></div></div>`; modal.showModal();
}

async function renderProposals() {
  view.innerHTML = `<div class="loading">Reading review queue</div>`;
  try { const data=await api("/api/proposals"); view.innerHTML=`<header class="section-head"><div><p class="eyebrow">Detect → propose → review → truth</p><h1 class="page-title">Proposals</h1><p class="page-subtitle">This is the optional review-first lane. Proposal patches change canonical knowledge only after a reviewed Apply; automatic evidence-backed maintenance is logged separately.</p></div></header><section>${data.proposals.map(row=>`<article class="list-row"><time>${esc(row.status.toUpperCase())}</time><div><h3>${esc(row.name)}</h3><p>${row.stale_count} stale signals · ${row.suggestion_count} structural suggestions · ${row.patch_count} explicit patches</p></div><button class="icon-button" data-proposal="${esc(row.name)}"><span>Review</span>${icon("scan-eye")}</button></article>`).join("") || `<p class="empty-state">No proposals are waiting in this project.</p>`}</section>`; view.querySelectorAll("[data-proposal]").forEach(node=>node.onclick=()=>openProposal(node.dataset.proposal)); } catch(error){renderError(error);}
}

async function openProposal(name) {
  const data=await api(`/api/proposals/${qs(name)}`); modalBody.innerHTML=`<div class="modal-inner"><p class="eyebrow">Proposal review · ${esc(data.document.review_status || "pending")}</p><h2>${esc(name)}</h2><p>${esc(data.document.notice || "Review the evidence and proposed patches before applying.")}</p><label class="field"><span>Reviewable proposal JSON — edit before Apply if needed</span><textarea id="proposal-json" class="proposal-json">${esc(JSON.stringify(data.document,null,2))}</textarea></label><div class="modal-actions"><button class="secondary" data-action="unresolved">Leave unresolved</button><button class="danger" data-action="reject">Reject</button><button class="primary" data-action="apply">Apply explicit patches</button></div></div>`; modal.showModal(); modalBody.querySelectorAll("[data-action]").forEach(node=>node.onclick=()=>proposalAction(name,node.dataset.action));
}

async function proposalAction(name, action) {
  try { const doc=JSON.parse(document.querySelector("#proposal-json").value); const result=await api(`/api/proposals/${qs(name)}`,{method:"POST",body:JSON.stringify({action,document:doc})}); modal.close(); toast(`Proposal ${result.status}`); await loadProject(); renderProposals(); } catch(error){toast(error.message);}
}

function renderError(error) { view.innerHTML=`<section><p class="eyebrow">Unable to open this surface</p><h1 class="page-title">Something broke the current.</h1><p class="page-subtitle">${esc(error.message)}</p><button class="primary" data-route="map">Return to map</button></section>`; }

document.addEventListener("click", event => {
  const routeNode=event.target.closest("[data-route]"); if(routeNode){route(routeNode.dataset.route);return;}
  const stageNode=event.target.closest("[data-stage]"); if(stageNode){route("stage",stageNode.dataset.stage);return;}
  if(event.target.closest("[data-close]")) modal.close();
});
document.querySelector("#global-search").addEventListener("submit", event => {event.preventDefault(); const query=document.querySelector("#search-input").value.trim(); if(query){state.searchQuery=query; route("search");}});
document.addEventListener("keydown", event => {if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){event.preventDefault();document.querySelector("#search-input").focus();}});
modal.addEventListener("click", event => {if(event.target===modal)modal.close();});

(async()=>{ try { await loadIcons(); await loadProject(); renderMap(); } catch(error){renderError(error);} })();
