const $ = (id) => document.getElementById(id);
let lastPayload = null;
let lastResult = null;

const defaults = {
  1: ["x1**2 - 2"],
  2: ["x1**2 + x2**2 - 4", "x1 - x2"],
  3: ["x1 + x2 + x3 - 6", "x1**2 + x2**2 + x3**2 - 14", "x1*x2*x3 - 6"]
};

function renderInputs() {
  const n = Number($("dimension").value);
  const eqWrap = $("equations"), xWrap = $("initial-values");
  const oldEq = [...eqWrap.querySelectorAll("input")].map(x => x.value);
  const oldX = [...xWrap.querySelectorAll("input")].map(x => x.value);
  eqWrap.innerHTML = ""; xWrap.innerHTML = "";
  for (let i = 0; i < n; i++) {
    const row = document.createElement("div"); row.className = "equation-row";
    const label = document.createElement("div"); label.className = "eq-label"; label.textContent = `F${i + 1}`;
    const input = document.createElement("input"); input.type = "text"; input.id = `eq-${i}`;
    input.placeholder = `Ej. x${i + 1}**2 - 4`; input.value = oldEq[i] ?? (defaults[n]?.[i] || "");
    row.append(label, input); eqWrap.append(row);

    const item = document.createElement("div"); item.className = "initial-item";
    const xLabel = document.createElement("label"); xLabel.textContent = `x${i + 1}⁽⁰⁾`;
    const xInput = document.createElement("input"); xInput.type = "number"; xInput.step = "any"; xInput.id = `x0-${i}`;
    const initial = n === 3 ? [0.5, 1.5, 2.5][i] : (n === 2 ? 1 : 1);
    xInput.value = oldX[i] ?? initial;
    item.append(xLabel, xInput); xWrap.append(item);
  }
}
$("dimension").addEventListener("change", renderInputs);
renderInputs();

function collectPayload() {
  const n = Number($("dimension").value);
  const equations = Array.from({ length: n }, (_, i) => $(`eq-${i}`).value);
  const x0 = Array.from({ length: n }, (_, i) => Number($(`x0-${i}`).value));
  const tolerance = Number($("tolerance").value), max_iter = Number($("max-iter").value);
  if (x0.some(v => !Number.isFinite(v))) throw new Error("Revisa los valores del punto inicial.");
  return { n, equations, x0, tolerance, max_iter, name: $("system-name").value };
}
function fmt(v, digits = 8) {
  if (v === null || v === undefined) return "—";
  if (!Number.isFinite(v)) return "∞";
  return Number(v).toPrecision(digits);
}
function matrixHTML(matrix) {
  return `<div class="matrix-table">${matrix.map(row => `<div class="matrix-row">${row.map(v => `<div class="matrix-cell">${escapeHTML(v)}</div>`).join("")}</div>`).join("")}</div>`;
}
function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function renderResults(result) {
  $("empty-state").classList.add("hidden");
  $("results").classList.remove("hidden");
  const status = $("status-card");
  status.textContent = result.message;
  status.className = "status-card" + (result.converged ? "" : " fail");
  $("solution-cards").innerHTML = result.solution
    ? result.solution.map((v, i) => `<div class="solution-card"><span>VARIABLE x${i + 1}*</span><strong>${fmt(v, 12)}</strong></div>`).join("")
    : `<div class="solution-card"><span>ESTADO</span><strong style="font-size:14px">Sin solución</strong></div>`;
  $("symbolic-system").innerHTML = `<div class="jacobian-title">SISTEMA F(x) = 0</div>${result.equations.map((e, i) => `<div class="symbolic-equation">F${i + 1}(x) = ${escapeHTML(e)}</div>`).join("")}<div class="jacobian-title">JACOBIANO SIMBÓLICO</div>${matrixHTML(result.jacobian_symbolic)}`;
  renderChart(result.history);
  const n = lastPayload.n;
  const headers = ["k", ...Array.from({ length: n }, (_, i) => `x${i + 1}`), ...Array.from({ length: n }, (_, i) => `F${i + 1}(x)`), "||F(x)||₂", "Error rel.", "Estado"];
  $("history-table").innerHTML = `<thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${result.history.map(r => `<tr><td>${r.iteration}</td>${r.x.map(v => `<td>${fmt(v, 7)}</td>`).join("")}${r.fx.map(v => `<td>${fmt(v, 5)}</td>`).join("")}<td>${fmt(r.absolute_error, 5)}</td><td>${fmt(r.relative_error, 5)}</td><td class="${r.converged ? "converged" : ""}">${r.converged ? "✓ Sí" : "—"}</td></tr>`).join("")}</tbody>`;
  $("iteration-details").innerHTML = result.history.map(r => `
    <div class="iteration-card">
      <button class="iteration-toggle" type="button"><span>Iteración k = ${r.iteration}</span><span>||F(x)||₂ = ${fmt(r.absolute_error, 5)}　⌄</span></button>
      <div class="iteration-content hidden">
        <div class="detail-block"><strong>VECTOR ACTUAL x⁽ᵏ⁾</strong><div class="vector-value">[ ${r.x.map(v => fmt(v, 10)).join(" , ")} ]</div></div>
        <div class="detail-block"><strong>RESIDUAL F(x⁽ᵏ⁾)</strong><div class="vector-value">[ ${r.fx.map(v => fmt(v, 8)).join(" , ")} ]</div></div>
        <div class="detail-block"><strong>JACOBIANO J(x⁽ᵏ⁾)</strong>${matrixHTML(r.jacobian.map(row => row.map(v => fmt(v, 7))))}</div>
        <div class="detail-block"><strong>INCREMENTO Δx</strong><div class="vector-value">${r.delta ? `[ ${r.delta.map(v => fmt(v, 10)).join(" , ")} ]` : "No se calculó en esta iteración."}</div>
          ${r.next_x ? `<strong style="margin-top:12px">NUEVO PUNTO x⁽ᵏ⁺¹⁾</strong><div class="vector-value">[ ${r.next_x.map(v => fmt(v, 10)).join(" , ")} ]</div>` : ""}
          ${r.converged ? '<div class="detail-note">✓ Tolerancia alcanzada. El método termina.</div>' : ""}
        </div>
      </div>
    </div>`).join("");
  document.querySelectorAll(".iteration-toggle").forEach(btn => btn.addEventListener("click", () => btn.nextElementSibling.classList.toggle("hidden")));
  if (window.MathJax) MathJax.typesetPromise();
}
function renderChart(history) {
  const wrap = $("convergence-chart");
  if (!history.length) { wrap.innerHTML = '<div class="chart-empty">No hay iteraciones para graficar.</div>'; return; }
  const values = history.map(r => Math.log10(Math.max(r.absolute_error, 1e-16)));
  const min = Math.min(...values), max = Math.max(...values);
  wrap.innerHTML = values.map((v, i) => {
    const height = max === min ? 75 : 12 + ((v - min) / (max - min)) * 78;
    return `<div class="chart-bar" style="height:${height}%"><span>${history[i].iteration}</span></div>`;
  }).join("");
}
$("solve-btn").addEventListener("click", async () => {
  const btn = $("solve-btn"); btn.disabled = true; btn.querySelector("span").textContent = "Calculando…";
  try {
    const payload = collectPayload(); lastPayload = payload;
    const response = await fetch("/api/solve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "No se pudo resolver el sistema.");
    lastResult = data.result; renderResults(lastResult);
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    alert(err.message);
  } finally { btn.disabled = false; btn.querySelector("span").textContent = "Calcular solución"; }
});
$("export-btn").addEventListener("click", async () => {
  if (!lastPayload) return;
  const btn = $("export-btn"); btn.disabled = true; btn.textContent = "Generando Excel…";
  try {
    const response = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lastPayload) });
    if (!response.ok) { const err = await response.json(); throw new Error(err.error || "Error al generar Excel."); }
    const blob = await response.blob(), url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "newton_raphson_educativo.xlsx"; a.click(); URL.revokeObjectURL(url);
  } catch (err) { alert(err.message); }
  finally { btn.disabled = false; btn.textContent = "↓ Exportar Excel educativo"; }
});
