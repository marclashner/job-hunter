const app = document.getElementById("app");

function route() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const detail = hash.match(/^\/jobs\/([0-9a-f-]{36})$/i);
  if (detail) {
    renderDetail(detail[1]);
    return;
  }
  renderDashboard();
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(detail);
  }
  return data;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pill(recommendation) {
  if (!recommendation) return `<span class="muted">Unevaluated</span>`;
  return `<span class="pill ${esc(recommendation)}">${esc(recommendation)}</span>`;
}

function decisionButtons(jobId, humanDecision, recommendation) {
  const recommended = recommendation === "apply";
  const current = humanDecision || "";
  return `
    <div class="actions">
      <button class="approve" data-decision="approve" data-id="${esc(jobId)}" ${current === "approve" ? "disabled" : ""}>Approve</button>
      <button class="review" data-decision="review" data-id="${esc(jobId)}" ${current === "review" ? "disabled" : ""}>Review</button>
      <button class="reject" data-decision="reject" data-id="${esc(jobId)}" ${current === "reject" ? "disabled" : ""}>Reject</button>
      ${recommended ? "" : `<span class="muted">Not an apply recommendation</span>`}
    </div>
  `;
}

async function sendDecision(jobId, decision) {
  return api(`/review/jobs/${jobId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

function bindDecisions(root, onDone) {
  root.querySelectorAll("button[data-decision]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      const id = button.getAttribute("data-id");
      const decision = button.getAttribute("data-decision");
      try {
        await sendDecision(id, decision);
        await onDone();
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

function queryFromForm(form) {
  const data = new FormData(form);
  const params = new URLSearchParams();
  for (const [key, value] of data.entries()) {
    if (value) params.set(key, value);
  }
  return params;
}

function _compensationFromJob(job) {
  const currency = job.salary_currency || "USD";
  if (job.salary_min == null && job.salary_max == null) return "Unlisted";
  if (job.salary_min != null && job.salary_max != null) {
    return `${Number(job.salary_min).toLocaleString()}-${Number(job.salary_max).toLocaleString()} ${currency}`;
  }
  if (job.salary_min != null) return `${Number(job.salary_min).toLocaleString()}+ ${currency}`;
  return `up to ${Number(job.salary_max).toLocaleString()} ${currency}`;
}

async function renderDashboard() {
  app.innerHTML = `<p class="muted">Loading dashboard…</p>`;
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  try {
    const [summary, queue] = await Promise.all([
      api("/review/summary"),
      api(`/review/jobs?${params.toString()}`),
    ]);
    app.innerHTML = `
      <section class="stats">
        <div class="stat"><strong>${summary.discovered_today}</strong><span>Jobs discovered today</span></div>
        <div class="stat"><strong>${summary.evaluated}</strong><span>Jobs evaluated</span></div>
        <div class="stat"><strong>${summary.recommended_applications}</strong><span>Recommended applications</span></div>
        <div class="stat"><strong>${summary.needing_review}</strong><span>Jobs needing review</span></div>
        <div class="stat"><strong>${summary.applications_submitted}</strong><span>Applications submitted</span></div>
        <div class="stat"><strong>${summary.interviews}</strong><span>Interviews</span></div>
        <div class="stat"><strong>${summary.offers}</strong><span>Offers</span></div>
      </section>
      <form class="filters" id="filters">
        <label>Recommendation
          <select name="recommendation">
            <option value="">All</option>
            <option value="apply">Apply</option>
            <option value="review">Review</option>
            <option value="reject">Reject</option>
          </select>
        </label>
        <label>Minimum score
          <input name="minimum_score" type="number" min="0" max="100" placeholder="0" />
        </label>
        <label>Source
          <select name="source">
            <option value="">All</option>
            <option value="manual">manual</option>
            <option value="greenhouse">greenhouse</option>
            <option value="lever">lever</option>
          </select>
        </label>
        <label>Remote
          <select name="remote_policy">
            <option value="">All</option>
            <option value="remote">remote</option>
            <option value="hybrid">hybrid</option>
            <option value="onsite">onsite</option>
          </select>
        </label>
        <label>Work location
          <select name="us_eligible">
            <option value="true">US eligible</option>
            <option value="false">All geos</option>
          </select>
        </label>
        <label>Date discovered
          <input name="discovered" type="date" />
        </label>
        <button type="submit">Filter</button>
      </form>
      <p class="muted">${queue.total} jobs in queue</p>
      <div style="overflow:auto">
        <table>
          <thead>
            <tr>
              <th>Company / title</th>
              <th>Location</th>
              <th>Compensation</th>
              <th>Score</th>
              <th>Recommendation</th>
              <th>Top strengths</th>
              <th>Concerns</th>
              <th>Human</th>
            </tr>
          </thead>
          <tbody>
            ${queue.items
              .map(
                (item) => `
              <tr>
                <td>
                  <a class="job-title" href="#/jobs/${item.id}">
                    ${esc(item.title)}
                    <span class="company">${esc(item.company)}</span>
                  </a>
                </td>
                <td>${esc(item.location || "—")}<div class="company">${esc((item.eligible_countries || []).join(", ") || item.remote_policy || "")}</div></td>
                <td>${esc(item.compensation)}${item.salary_source ? `<div class="company">${esc(item.salary_source)}</div>` : ""}</td>
                <td>${item.score == null ? "—" : item.score}</td>
                <td>${pill(item.recommendation)}</td>
                <td>${item.top_strengths.map((row) => esc(row)).join("<br>") || "—"}</td>
                <td>${item.concerns.map((row) => esc(row)).join("<br>") || "—"}</td>
                <td>
                  ${item.human_decision ? `<div class="muted">Decision: ${esc(item.human_decision)}</div>` : ""}
                  ${decisionButtons(item.id, item.human_decision, item.recommendation)}
                </td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
    const form = document.getElementById("filters");
    if (!params.has("us_eligible")) form.elements.us_eligible.value = "true";
    for (const [key, value] of params.entries()) {
      if (form.elements[key]) form.elements[key].value = value;
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      location.hash = `#/?${queryFromForm(form).toString()}`;
    });
    bindDecisions(app, renderDashboard);
  } catch (error) {
    app.innerHTML = `<p class="error">${esc(error.message)}</p>`;
  }
}

async function renderDetail(jobId) {
  app.innerHTML = `<p class="muted">Loading job…</p>`;
  try {
    const detail = await api(`/review/jobs/${jobId}`);
    const evaluation = detail.evaluation;
    const hard = detail.hard_filter;
    app.innerHTML = `
      <p><a href="#/">← Queue</a></p>
      <div class="detail">
        <section class="card">
          <h2>${esc(detail.job.title)}</h2>
          <p class="muted">${esc(detail.job.company)} · ${esc(detail.job.location || "Location unknown")} · ${esc(detail.job.remote_policy || "")} · ${(detail.job.eligible_countries || []).join(", ") || "geo unknown"}</p>
          <p>${pill(evaluation?.recommendation)} ${evaluation ? `score ${evaluation.overall_score}` : ""} ${detail.human_decision ? `· human ${esc(detail.human_decision)}` : ""}</p>
          ${decisionButtons(detail.job.id, detail.human_decision, evaluation?.recommendation)}
          <h3>Compensation</h3>
          <p>${esc(_compensationFromJob(detail.job))} ${detail.job.salary_source ? `<span class="muted">(${esc(detail.job.salary_source)})</span>` : ""}</p>
          ${detail.job.salary_quote ? `<pre>${esc(detail.job.salary_quote)}</pre>` : ""}
          <h3>Description</h3>
          <pre>${esc(detail.job.description)}</pre>
          <h3>Application URL</h3>
          ${
            detail.application_url
              ? `<p><a href="${esc(detail.application_url)}" target="_blank" rel="noreferrer">${esc(detail.application_url)}</a></p><p class="muted">Opening the URL does not submit an application.</p>`
              : `<p class="muted">No application URL on this listing.</p>`
          }
        </section>
        <section class="card">
          <h3>Evaluation</h3>
          ${
            evaluation
              ? `
            <p>${pill(evaluation.recommendation)} · ${esc(evaluation.evaluation_mode)} · ${esc(evaluation.model || "no model")}</p>
            <p>tech ${evaluation.technical_fit} · domain ${evaluation.domain_fit} · product ${evaluation.product_fit} · ai ${evaluation.ai_relevance} · seniority ${evaluation.seniority_fit} · company ${evaluation.company_interest_fit} · evidence ${evaluation.evidence_strength}</p>
            <p><strong>Reasoning</strong></p>
            <pre>${esc(evaluation.reasoning)}</pre>
            <p><strong>Strengths</strong></p>
            <pre>${esc((evaluation.strengths || []).join("\n") || "—")}</pre>
            <p><strong>Concerns</strong></p>
            <pre>${esc((evaluation.concerns || []).join("\n") || "—")}</pre>
          `
              : `<p class="muted">Not evaluated yet.</p>`
          }
          <h3>Hard filter</h3>
          ${
            hard
              ? `<pre>passed: ${hard.passed}
failed: ${(hard.failed_rules || []).join(", ") || "none"}
missing: ${(hard.missing_information || []).join(", ") || "none"}
warnings: ${(hard.warnings || []).join(", ") || "none"}</pre>`
              : `<p class="muted">No hard-filter result stored.</p>`
          }
          <h3>Supporting candidate evidence</h3>
          ${
            detail.supporting_evidence.length
              ? detail.supporting_evidence
                  .map(
                    (item) => `
              <div class="evidence">
                <strong>${esc(item.claim)}</strong>
                <div class="muted">${esc(item.category)} · ${esc(item.confidence)}</div>
                <pre>${esc(item.detailed_description)}</pre>
              </div>`
                  )
                  .join("")
              : `<p class="muted">No cited evidence.</p>`
          }
        </section>
      </div>
    `;
    bindDecisions(app, () => renderDetail(jobId));
  } catch (error) {
    app.innerHTML = `<p class="error">${esc(error.message)}</p>`;
  }
}

window.addEventListener("hashchange", route);
route();
