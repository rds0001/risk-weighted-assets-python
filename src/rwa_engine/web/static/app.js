"use strict";

const state = { datasets: [], detail: null, selectedRun: null };
const $ = (id) => document.getElementById(id);

const money = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("de-DE", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const number = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });

function formatBytes(value) {
  if (!Number.isFinite(value)) return "–";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "–";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString("de-DE");
}

function el(tag, attrs = {}, text = null) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  if (text !== null) node.textContent = text;
  return node;
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let body;
  try { body = await response.json(); } catch { body = { message: `HTTP ${response.status}` }; }
  if (!response.ok) throw new Error(body.message || `HTTP ${response.status}`);
  return body;
}

function setStatus(ok, message) {
  const target = $("server-status");
  target.className = `status ${ok ? "good" : "bad"}`;
  target.textContent = message;
}

function setMessage(message = "", kind = "") {
  const target = $("run-message");
  target.className = `message ${kind}`;
  target.textContent = message;
}

function downloadUrl(area, file, run = null) {
  const query = new URLSearchParams({ dataset: state.detail.id, area, file });
  if (run) query.set("run", run);
  return `/files?${query}`;
}

async function loadDatasets(preserve = true) {
  const previous = preserve ? $("dataset-select").value : "";
  const body = await request("/api/datasets");
  state.datasets = body.datasets;
  const select = $("dataset-select");
  select.replaceChildren();
  for (const item of state.datasets) {
    const label = `${item.as_of_date} · ${item.version} · ${item.bank_profile}`;
    select.append(el("option", { value: item.id }, label));
  }
  if (previous && state.datasets.some((item) => item.id === previous)) select.value = previous;
  if (!state.datasets.length) {
    setMessage("Keine Datensätze unter der konfigurierten Datenwurzel gefunden.", "error");
    renderEmpty();
    return;
  }
  await loadDetail(select.value);
}

async function loadDetail(identifier) {
  state.detail = await request(`/api/dataset?${new URLSearchParams({ dataset: identifier })}`);
  state.selectedRun = state.detail.runs[0]?.run_id || null;
  render();
}

function render() {
  renderMeta();
  renderInputs();
  renderRunSelect();
  renderRun();
}

function renderEmpty() {
  $("dataset-meta").replaceChildren();
  $("metrics").replaceChildren();
  $("input-table").replaceChildren();
  $("output-files").replaceChildren(el("p", { class: "empty" }, "Keine Ergebnisse vorhanden"));
}

function renderMeta() {
  const m = state.detail.manifest;
  const items = [
    ["Stichtag", m.as_of_date], ["Datenversion", m.dataset_version], ["Bankprofil", m.bank_profile],
    ["Fachtabellen", number.format(m.table_count || 0)], ["Inputzeilen", number.format(m.row_count || 0)],
  ];
  const target = $("dataset-meta");
  target.replaceChildren(...items.map(([label, value]) => {
    const box = el("div", { class: "meta-item" });
    box.append(el("span", {}, label), el("strong", {}, value || "–"));
    return box;
  }));
}

function renderInputs() {
  const target = $("input-table");
  target.replaceChildren();
  for (const item of state.detail.inputs) {
    const row = el("tr");
    const link = el("a", { class: "download", href: downloadUrl("input", item.name) }, "Download");
    const stateLabel = item.integrity === "MATCH" ? "Unverändert" : item.integrity === "CHANGED" ? "Bearbeitet" : "Nicht deklariert";
    const stateClass = item.integrity === "MATCH" ? "match" : "changed";
    const stateCell = el("td");
    stateCell.append(el("span", { class: `file-state ${stateClass}` }, stateLabel));
    row.append(el("td", {}, item.name), el("td", {}, String(item.table_count ?? "–")),
      el("td", {}, item.row_count == null ? "–" : number.format(item.row_count)),
      stateCell, el("td", {}, formatBytes(item.size_bytes)), el("td"));
    row.lastChild.append(link);
    target.append(row);
  }
  const missing = state.detail.manifest.missing_inputs;
  const changed = state.detail.manifest.changed_inputs;
  const badge = $("input-badge");
  badge.textContent = missing.length ? `${missing.length} fehlen` : changed.length ? `${changed.length} bearbeitet` : `${state.detail.inputs.length}/${state.detail.manifest.expected_input_count} vollständig`;
  badge.className = `badge ${missing.length ? "bad" : changed.length ? "changed" : ""}`;
}

function renderRunSelect() {
  const select = $("run-select");
  select.replaceChildren();
  if (!state.detail.runs.length) {
    select.append(el("option", { value: "" }, "Noch kein Lauf"));
    select.disabled = true;
    return;
  }
  select.disabled = false;
  for (const run of state.detail.runs) {
    select.append(el("option", { value: run.run_id }, `${run.run_id.replace("RUN-", "")} · ${run.status}`));
  }
  select.value = state.selectedRun;
}

function metric(label, value, hint = "") {
  const box = el("div", { class: "metric" });
  box.append(el("span", {}, label), el("strong", {}, value), el("small", {}, hint));
  return box;
}

function renderRun() {
  const run = state.detail.runs.find((item) => item.run_id === state.selectedRun);
  if (!run) {
    $("metrics").replaceChildren(metric("Status", "Noch kein Lauf", "Gesamtlauf starten"));
    $("run-summary").replaceChildren();
    $("output-files").replaceChildren(el("p", { class: "empty" }, "Noch keine Output-Workbooks vorhanden."));
    return;
  }
  const m = run.metrics || {};
  const cards = [
    metric("TREA", money.format(m.TREA || 0), "Säule 1, angewandte Sicht"),
    metric("CET1-Quote", percent.format(m.CET1_RATIO || 0), `CET1 ${money.format(m.CET1 || 0)}`),
    metric("Gesamtkapitalquote", percent.format(m.TOTAL_CAPITAL_RATIO || 0), `Eigenmittel ${money.format(m.TOTAL_OWN_FUNDS || 0)}`),
    metric("Output Floor", m.FLOOR_BINDING ? "Bindend" : "Nicht bindend", `Uplift ${money.format(m.FLOOR_UPLIFT || 0)}`),
    metric("EVE-SOT", percent.format(m.EVE_SOT_RATIO || 0), `Verlust ${money.format(m.WORST_EVE_LOSS || 0)}`),
    metric("NII-SOT", percent.format(m.NII_SOT_RATIO || 0), `Rückgang ${money.format(m.WORST_NII_DECLINE || 0)}`),
    metric("Ökonomischer Headroom", money.format(m.ECONOMIC_HEADROOM || 0), `EC ${money.format(m.EC_AGGREGATE || 0)}`),
    metric("Kontrollen", `${run.controls_passed}/${run.control_count}`, `${run.validation_errors} Fehler · ${run.validation_warnings} Warnungen`),
  ];
  $("metrics").replaceChildren(...cards);

  const summary = $("run-summary");
  const fields = [["Lauf-ID", run.run_id], ["Status", run.status], ["Regelsatz", run.rule_set_id || "–"],
    ["Validierung", `${run.validation_errors} Fehler / ${run.validation_warnings} Warnungen`], ["Erstellt", formatDate(run.created_at)]];
  summary.replaceChildren(...fields.map(([label, value]) => {
    const box = el("div"); box.append(el("span", {}, label), el("strong", {}, value)); return box;
  }));

  const output = $("output-files");
  output.replaceChildren(...run.files.map((file) => {
    const link = el("a", { href: downloadUrl("output", file.name, run.run_id) });
    link.append(el("span", {}, file.name), el("span", {}, formatBytes(file.size_bytes)));
    return link;
  }));
}

async function executeRun() {
  if (!state.detail) return;
  const button = $("run-button");
  button.disabled = true;
  $("refresh-button").disabled = true;
  $("dataset-select").disabled = true;
  setMessage("Gesamtlauf läuft. Validierung, Berechnung und Excel-Export werden vollständig ausgeführt …");
  try {
    const body = await request("/api/run", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset: state.detail.id }) });
    state.detail = body.dataset;
    state.selectedRun = body.run_id;
    render();
    setMessage(`Lauf ${body.run_id} erfolgreich abgeschlossen.`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
    $("refresh-button").disabled = false;
    $("dataset-select").disabled = false;
  }
}

async function boot() {
  try {
    await request("/api/health");
    setStatus(true, "Backend bereit");
    await loadDatasets(false);
  } catch (error) {
    setStatus(false, "Backend nicht erreichbar");
    setMessage(error.message, "error");
  }
}

$("dataset-select").addEventListener("change", (event) => loadDetail(event.target.value).catch((error) => setMessage(error.message, "error")));
$("run-select").addEventListener("change", (event) => { state.selectedRun = event.target.value; renderRun(); });
$("refresh-button").addEventListener("click", () => loadDatasets().catch((error) => setMessage(error.message, "error")));
$("run-button").addEventListener("click", executeRun);
boot();
