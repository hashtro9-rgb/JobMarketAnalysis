/* Job Market Intelligence Dashboard */

Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';
Chart.defaults.font.family = 'Inter';
Chart.defaults.maintainAspectRatio = false;

const C = { blue: '#388bfd', cyan: '#00d4ff', purple: '#7c3aed', green: '#3fb950', orange: '#db6d28' };
const DATA = {};
const CHARTS = {};
const FILES = ['summary', 'skills', 'companies', 'countries', 'distributions',
  'salary_by_experience', 'monthly_trend', 'skill_pairs', 'salary_distribution', 'jobs'];

async function boot() {
  try {
    const results = await Promise.all(FILES.map(f => fetch(`data/${f}.json`).then(r => r.json())));
    FILES.forEach((f, i) => { DATA[f] = results[i]; });
    init();
  } catch (e) {
    console.error(e);
    document.querySelector('.main').innerHTML =
      `<div style="padding:40px;color:#f85149">Failed to load dashboard data: ${e.message}</div>`;
  }
}
document.addEventListener('DOMContentLoaded', boot);

const fmt = n => (n == null || isNaN(n)) ? '—' : Number(n).toLocaleString('en-US');
const fmtUSD = n => (n == null || isNaN(n)) ? '—' : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });

function kpi(label, value, sub) {
  return `<div class="kpi-card"><div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>${sub ? `<div class="kpi-sub">${sub}</div>` : ''}</div>`;
}

const RENDERERS = {};
const rendered = new Set();
function renderTab(tab) {
  if (!rendered.has(tab)) {
    try { (RENDERERS[tab] || (() => {}))(); } catch (e) { console.error(tab, e); }
    rendered.add(tab);
  }
  Object.values(CHARTS).forEach(c => { try { c.resize(); } catch (e) {} });
}

function init() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('tab-' + item.dataset.tab).classList.add('active');
      renderTab(item.dataset.tab);
    });
  });

  const s = DATA.summary;
  document.getElementById('footer-note').textContent =
    `${s.date_range_start} to ${s.date_range_end} · ${s.total_jobs} postings`;

  renderTab('overview');
}

function makeChart(canvasId, type, data, options) {
  const ctx = document.getElementById(canvasId);
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  CHARTS[canvasId] = new Chart(ctx, { type, data, options: options || {} });
}

function baseScales(extra) {
  return { x: { grid: { color: '#1c2333' } }, y: { grid: { color: '#1c2333' }, beginAtZero: true }, ...extra };
}

/* ---------------- OVERVIEW ---------------- */
RENDERERS.overview = function () {
  const s = DATA.summary;
  document.getElementById('overview-kpis').innerHTML = [
    kpi('Total Postings', fmt(s.total_jobs), `${s.date_range_start} → ${s.date_range_end}`),
    kpi('Companies Hiring', fmt(s.total_companies)),
    kpi('Avg Salary', fmtUSD(s.avg_salary_usd), `${s.salary_coverage_pct}% of postings disclose salary`),
    kpi('Remote Share', s.remote_pct + '%', `${s.hybrid_count} hybrid, 0 on-site`),
    kpi('Top Skill', s.top_skill),
    kpi('Top Country', s.top_country),
  ].join('');

  const top = DATA.skills.slice().sort((a, b) => b.postings - a.postings).slice(0, 10);
  makeChart('chart-top-skills', 'bar', {
    labels: top.map(d => d.skill),
    datasets: [{ data: top.map(d => d.postings), backgroundColor: C.blue }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });

  const setup = DATA.distributions.work_setup;
  makeChart('chart-work-setup', 'doughnut', {
    labels: Object.keys(setup),
    datasets: [{ data: Object.values(setup), backgroundColor: [C.blue, C.purple, C.green] }],
  }, { plugins: { legend: { position: 'bottom', labels: { boxWidth: 8 } } } });

  const expOrder = ['Entry Level', 'Mid Level', 'Senior Level', 'Lead/Principal', 'Not Specified'];
  const exp = DATA.distributions.experience_level;
  makeChart('chart-experience', 'doughnut', {
    labels: expOrder.filter(k => exp[k]),
    datasets: [{ data: expOrder.filter(k => exp[k]).map(k => exp[k]),
      backgroundColor: [C.green, C.blue, C.purple, C.orange, '#484f58'] }],
  }, { plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, font: { size: 9 } } } } });

  const monthly = DATA.monthly_trend;
  makeChart('chart-monthly-overview', 'line', {
    labels: monthly.map(d => d.posting_month),
    datasets: [{ data: monthly.map(d => d.postings), borderColor: C.cyan, backgroundColor: C.cyan, tension: 0.3 }],
  }, { plugins: { legend: { display: false } }, scales: baseScales() });
};

/* ---------------- SKILLS ---------------- */
RENDERERS.skills = function () {
  const all = DATA.skills.slice().sort((a, b) => b.postings - a.postings);
  makeChart('chart-all-skills', 'bar', {
    labels: all.map(d => d.skill),
    datasets: [{ data: all.map(d => d.postings), backgroundColor: C.blue }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });

  const pairs = DATA.skill_pairs.slice(0, 15);
  makeChart('chart-skill-pairs', 'bar', {
    labels: pairs.map(d => `${d.skill_a} + ${d.skill_b}`),
    datasets: [{ data: pairs.map(d => d.co_occurrences), backgroundColor: C.purple }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });

  const withSalary = DATA.skills.filter(d => d.avg_salary != null);
  makeChart('chart-skill-scatter', 'scatter', {
    datasets: [{
      label: 'Skills', backgroundColor: C.green,
      data: withSalary.map(d => ({ x: d.postings, y: d.avg_salary, label: d.skill })),
    }],
  }, {
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => `${ctx.raw.label}: ${ctx.raw.x} postings, ${fmtUSD(ctx.raw.y)}` } },
    },
    scales: { x: { title: { display: true, text: 'Demand (# postings)' }, grid: { color: '#1c2333' } },
              y: { title: { display: true, text: 'Avg Salary (USD)' }, grid: { color: '#1c2333' } } },
  });
};

/* ---------------- SALARY ---------------- */
RENDERERS.salary = function () {
  const s = DATA.summary;
  document.getElementById('salary-kpis').innerHTML = [
    kpi('Avg Salary', fmtUSD(s.avg_salary_usd)),
    kpi('Median Salary', fmtUSD(s.median_salary_usd)),
    kpi('Salary Coverage', s.salary_coverage_pct + '%', 'of all postings'),
  ].join('');

  const values = DATA.salary_distribution;
  const min = Math.min(...values), max = Math.max(...values);
  const nBins = 20, width = (max - min) / nBins || 1;
  const bins = new Array(nBins).fill(0);
  values.forEach(v => { let i = Math.floor((v - min) / width); if (i >= nBins) i = nBins - 1; if (i < 0) i = 0; bins[i]++; });
  makeChart('chart-salary-hist', 'bar', {
    labels: bins.map((_, i) => '$' + Math.round((min + i * width) / 1000) + 'K'),
    datasets: [{ data: bins, backgroundColor: C.blue }],
  }, { plugins: { legend: { display: false } }, scales: baseScales() });

  const byExp = DATA.salary_by_experience;
  makeChart('chart-salary-experience', 'bar', {
    labels: byExp.map(d => d.experience_level),
    datasets: [{ data: byExp.map(d => d.avg_salary), backgroundColor: C.green }],
  }, { plugins: { legend: { display: false } }, scales: baseScales() });

  const bySkill = DATA.skills.filter(d => d.n_salaried >= 3).sort((a, b) => b.avg_salary - a.avg_salary);
  makeChart('chart-salary-skill', 'bar', {
    labels: bySkill.map(d => d.skill),
    datasets: [{ data: bySkill.map(d => d.avg_salary), backgroundColor: C.cyan }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });

  const byCompany = DATA.companies.filter(d => d.n_salaried >= 2 && d.avg_salary != null)
    .sort((a, b) => b.avg_salary - a.avg_salary).slice(0, 15);
  makeChart('chart-salary-company', 'bar', {
    labels: byCompany.map(d => d.company),
    datasets: [{ data: byCompany.map(d => d.avg_salary), backgroundColor: C.orange }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });
};

/* ---------------- GEOGRAPHY ---------------- */
RENDERERS.geography = function () {
  const top = DATA.countries.slice(0, 20);
  makeChart('chart-countries', 'bar', {
    labels: top.map(d => d.country),
    datasets: [{ data: top.map(d => d.postings), backgroundColor: C.blue }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });

  const thead = document.querySelector('#table-countries thead');
  const tbody = document.querySelector('#table-countries tbody');
  thead.innerHTML = '<tr><th>Country</th><th>Postings</th></tr>';
  tbody.innerHTML = DATA.countries.map(d => `<tr><td>${d.country}</td><td>${fmt(d.postings)}</td></tr>`).join('');
};

/* ---------------- TRENDS ---------------- */
RENDERERS.trends = function () {
  const monthly = DATA.monthly_trend;
  makeChart('chart-monthly-trend', 'line', {
    labels: monthly.map(d => d.posting_month),
    datasets: [{ data: monthly.map(d => d.postings), borderColor: C.cyan, backgroundColor: C.cyan, tension: 0.3, fill: false }],
  }, { plugins: { legend: { display: false } }, scales: baseScales() });

  const top = DATA.companies.slice(0, 15);
  makeChart('chart-top-companies', 'bar', {
    labels: top.map(d => d.company),
    datasets: [{ data: top.map(d => d.postings), backgroundColor: C.purple }],
  }, { indexAxis: 'y', plugins: { legend: { display: false } }, scales: baseScales() });
};

/* ---------------- JOBS ---------------- */
const filterState = { search: '', experience: 'all', setup: 'all' };
RENDERERS.jobs = function () {
  const exps = [...new Set(DATA.jobs.map(j => j.experience_level))].filter(Boolean);
  const setups = [...new Set(DATA.jobs.map(j => j.work_setup))].filter(Boolean);
  const expSel = document.getElementById('f-experience');
  const setupSel = document.getElementById('f-setup');
  exps.forEach(e => expSel.insertAdjacentHTML('beforeend', `<option value="${e}">${e}</option>`));
  setups.forEach(s => setupSel.insertAdjacentHTML('beforeend', `<option value="${s}">${s}</option>`));

  document.getElementById('f-search').addEventListener('input', e => { filterState.search = e.target.value.toLowerCase(); renderJobsTable(); });
  expSel.addEventListener('change', e => { filterState.experience = e.target.value; renderJobsTable(); });
  setupSel.addEventListener('change', e => { filterState.setup = e.target.value; renderJobsTable(); });

  renderJobsTable();
};

function renderJobsTable() {
  let rows = DATA.jobs.filter(j => {
    if (filterState.experience !== 'all' && j.experience_level !== filterState.experience) return false;
    if (filterState.setup !== 'all' && j.work_setup !== filterState.setup) return false;
    if (filterState.search) {
      const hay = `${j.job_title} ${j.company_name}`.toLowerCase();
      if (!hay.includes(filterState.search)) return false;
    }
    return true;
  }).slice(0, 300);

  document.getElementById('result-count').textContent = `${rows.length} of ${DATA.jobs.length} shown`;

  const thead = document.querySelector('#table-jobs thead');
  const tbody = document.querySelector('#table-jobs tbody');
  thead.innerHTML = '<tr><th>Title</th><th>Company</th><th>Country</th><th>Setup</th><th>Experience</th><th>Salary (USD)</th><th>Skills</th><th></th></tr>';
  tbody.innerHTML = rows.map(j => `
    <tr>
      <td>${j.job_title || ''}</td>
      <td>${j.company_name || ''}</td>
      <td>${j.primary_country || '—'}</td>
      <td><span class="badge">${j.work_setup || '—'}</span></td>
      <td>${j.experience_level || '—'}</td>
      <td>${j.salary_avg_usd_annual ? fmtUSD(j.salary_avg_usd_annual) : '—'}</td>
      <td>${(j.skills_list || []).slice(0, 3).join(', ')}</td>
      <td><a href="${j.job_url}" target="_blank" rel="noopener">↗</a></td>
    </tr>`).join('');
}
