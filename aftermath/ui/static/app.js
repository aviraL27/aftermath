// Aftermath Dashboard Client Application — TermUI Edition (https://www.termui.io)

let tasks = [];
let selectedTask = null;
let lastTrace = null;

// ==========================================
// 1. TermUI Custom Follower Cursor Physics
// ==========================================
function initCustomCursor() {
  const ring = document.getElementById('cursor-ring');
  if (!ring) return;

  window.addEventListener('mousemove', (e) => {
    ring.style.transform = `translate(${e.clientX}px, ${e.clientY}px) translate(-50%, -50%)`;
  });

  // Hover detection
  const interactiveSelector = 'button, a, select, input, .task-card, .btn';
  document.addEventListener('mouseover', (e) => {
    if (e.target.closest(interactiveSelector)) {
      ring.classList.add('active-hover');
    }
  });

  document.addEventListener('mouseout', (e) => {
    if (e.target.closest(interactiveSelector)) {
      ring.classList.remove('active-hover');
    }
  });
}

// ==========================================
// 2. Matrix Rain Background Canvas
// ==========================================
function initMatrixRain() {
  const canvas = document.getElementById('matrix-rain');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const chars = '0123456789ABCDEF$#%*+-><_アイウエオカキクケコサシスセソタチツテト';
  const fontSize = 14;
  const columns = Math.floor(width / fontSize);
  const drops = Array(columns).fill(1);

  function draw() {
    ctx.fillStyle = 'rgba(10, 11, 16, 0.08)';
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#00ff88';
    ctx.font = `${fontSize}px "JetBrains Mono", monospace`;

    for (let i = 0; i < drops.length; i++) {
      const text = chars.charAt(Math.floor(Math.random() * chars.length));
      ctx.fillText(text, i * fontSize, drops[i] * fontSize);

      if (drops[i] * fontSize > height && Math.random() > 0.985) {
        drops[i] = 0;
      }
      drops[i]++;
    }
  }

  setInterval(draw, 45);
}

// ==========================================
// 3. API & Task Management
// ==========================================
async function loadSystemStatus() {
  try {
    const res = await fetch('/api/system-status');
    const data = await res.json();
    const e2bPill = document.getElementById('status-e2b');
    const gemmaPill = document.getElementById('status-gemma');
    const mistralPill = document.getElementById('status-mistral');

    if (e2bPill) {
      e2bPill.innerHTML = `<span class="pill-dot"></span><span>E2B Cloud: ${data.e2b_configured ? 'Firecracker Linux Micro-VM (Active)' : 'Inactive'}</span>`;
    }
    if (gemmaPill) {
      gemmaPill.innerHTML = `<span class="pill-dot"></span><span>Gemma 4: ${data.google_api_configured ? 'Google API (2.4s)' : 'Ollama Local'}</span>`;
    }
    if (mistralPill) {
      mistralPill.innerHTML = `<span class="pill-dot"></span><span>Mistral: ${data.mistral_model}</span>`;
    }
  } catch (e) {
    console.error('Failed to load system status:', e);
  }
}

async function loadTasks() {
  try {
    const res = await fetch('/api/tasks');
    tasks = await res.json();
    renderTaskList();
    document.getElementById('tasks-count').textContent = `${tasks.length} tasks`;

    // Default select E2B demo task if present, otherwise first task
    if (tasks.length > 0 && !selectedTask) {
      const e2bTask = tasks.find(t => t.id.includes('e2b'));
      selectTask(e2bTask || tasks[0]);
    }
  } catch (e) {
    console.error('Failed to load tasks:', e);
  }
}

function renderTaskList() {
  const container = document.getElementById('task-list-container');
  if (!container) return;

  if (tasks.length === 0) {
    container.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 12px;">No tasks found.</div>';
    return;
  }

  container.innerHTML = tasks.map(t => {
    const isE2B = (t.sandbox_backend === 'e2b') || t.id.includes('e2b');
    return `
      <div class="task-card ${selectedTask && selectedTask.id === t.id ? 'selected' : ''}" onclick="window.onSelectTask('${t.id}')">
        <div class="task-card-title">${escapeHtml(t.name)}</div>
        <div class="task-card-meta">
          <span class="badge-tag ${isE2B ? 'e2b' : (t.is_regression_test ? 'regression' : 'standard')}">
            ${isE2B ? 'E2B VM' : (t.is_regression_test ? 'Regression' : 'Local')}
          </span>
          <span>${t.invariants_count} Invariants</span>
          <span>${t.assertions_count} Assertions</span>
        </div>
      </div>
    `;
  }).join('');
}

window.onSelectTask = function(taskId) {
  const t = tasks.find(x => x.id === taskId);
  if (t) selectTask(t);
};

function selectTask(task) {
  selectedTask = task;
  renderTaskList();

  document.getElementById('active-task-name').textContent = task.name;
  document.getElementById('active-task-desc').textContent = task.description || 'Task ready for sandboxed execution.';
  document.getElementById('active-task-instruction').textContent = task.instruction || task.description || 'Updating workspace...';

  const backendBadge = document.getElementById('active-task-backend');
  const isE2B = (task.sandbox_backend === 'e2b') || task.id.includes('e2b');
  backendBadge.textContent = isE2B ? 'E2B MICRO-VM' : 'LOCAL SANDBOX';
  backendBadge.className = `badge-tag ${isE2B ? 'e2b' : 'standard'}`;

  // Sync backend select dropdown
  const backendSelect = document.getElementById('backend-select');
  if (backendSelect) {
    backendSelect.value = isE2B ? 'e2b' : 'local';
  }

  const badge = document.getElementById('task-badge');
  if (task.is_regression_test) {
    badge.style.display = 'inline-block';
    badge.textContent = task.validated ? 'Validated Regression' : 'Generated Test';
    badge.className = 'badge-status pass';
  } else {
    badge.style.display = 'none';
  }

  // Hide run panels until execution
  document.getElementById('result-panel').style.display = 'none';
  document.getElementById('diff-panel').style.display = 'none';
  document.getElementById('trace-panel').style.display = 'none';
  document.getElementById('compare-panel').style.display = 'none';
}

async function runCurrentTask() {
  if (!selectedTask) return;
  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  btn.textContent = 'Executing in Sandbox...';

  const model = document.getElementById('model-select').value;
  const backend = document.getElementById('backend-select').value;

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_file: selectedTask.file_path,
        model: model,
        backend: backend
      })
    });

    const trace = await res.json();
    lastTrace = trace;
    renderRunResults(trace);
  } catch (e) {
    alert('Execution error: ' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = '>_ Execute Task';
  }
}

function renderRunResults(trace) {
  // 1. Result Status & Matrix
  const resultPanel = document.getElementById('result-panel');
  resultPanel.style.display = 'block';

  const statusBadge = document.getElementById('run-status-badge');
  statusBadge.textContent = trace.status;
  statusBadge.className = `badge-status ${trace.status === 'PASSED' ? 'pass' : 'fail'}`;

  const btnGen = document.getElementById('btn-generate-test');
  btnGen.style.display = (trace.status === 'FAILED') ? 'inline-flex' : 'none';
  document.getElementById('generate-message').style.display = 'none';

  const assertionsContainer = document.getElementById('assertions-container');
  const items = [];

  // Assertions
  for (const a of trace.assertion_results) {
    const passed = a.passed;
    const label = a.spec.command ? `COMMAND: ${a.spec.command}` : (a.spec.key_path || a.spec.path);
    items.push(`
      <div class="assertion-item ${passed ? 'passed' : 'failed'}">
        <div>
          <span style="color:var(--cyan); font-size:10px; margin-right:8px; font-weight:700;">ASSERTION</span>
          <strong>${escapeHtml(label)}</strong>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="color:var(--text-muted); font-size:11px;">${passed ? String(a.actual_value) : escapeHtml(a.error_message || '')}</span>
          <span class="badge-status ${passed ? 'pass' : 'fail'}">${passed ? 'PASS' : 'FAIL'}</span>
        </div>
      </div>
    `);
  }

  // Invariants
  for (const inv of trace.invariant_results) {
    const passed = inv.passed;
    const label = inv.spec.command ? `INVARIANT COMMAND: ${inv.spec.command}` : (inv.spec.key_path || inv.spec.path);
    items.push(`
      <div class="assertion-item ${passed ? 'passed' : 'failed'}">
        <div>
          <span style="color:var(--accent); font-size:10px; margin-right:8px; font-weight:700;">INVARIANT</span>
          <strong>${escapeHtml(label)}</strong>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="color:var(--text-muted); font-size:11px;">${passed ? String(inv.actual_value) : escapeHtml(inv.error_message || '')}</span>
          <span class="badge-status ${passed ? 'pass' : 'fail'}">${passed ? 'PASS' : 'VIOLATED'}</span>
        </div>
      </div>
    `);
  }

  assertionsContainer.innerHTML = items.join('');

  // 2. Diff Panel
  const diffPanel = document.getElementById('diff-panel');
  if (trace.workspace_diff && trace.workspace_diff.trim()) {
    diffPanel.style.display = 'block';
    const lines = trace.workspace_diff.split('\n');
    document.getElementById('diff-summary').textContent = `${lines.length} lines modified`;

    const formattedDiff = lines.map(line => {
      if (line.startsWith('+')) return `<span class="diff-add">${escapeHtml(line)}</span>`;
      if (line.startsWith('-')) return `<span class="diff-del">${escapeHtml(line)}</span>`;
      return escapeHtml(line);
    }).join('\n');

    document.getElementById('diff-content').innerHTML = formattedDiff;
  } else {
    diffPanel.style.display = 'none';
  }

  // 3. Trace Steps
  const tracePanel = document.getElementById('trace-panel');
  tracePanel.style.display = 'block';
  document.getElementById('trace-duration').textContent = `${trace.duration_seconds.toFixed(2)}s (${trace.steps.length} steps)`;

  const stepsContainer = document.getElementById('trace-steps-container');
  stepsContainer.innerHTML = trace.steps.map(s => `
    <div class="step-item">
      <div class="step-header">
        <span class="step-num">Step ${s.step_number}</span>
        ${s.tool_name ? `<span class="step-tool">${s.tool_name}</span>` : '<span style="color:var(--text-muted);">Finish</span>'}
        <span style="color:var(--text-muted); font-size:11px; margin-left:auto;">${s.duration_seconds.toFixed(2)}s</span>
      </div>
      ${s.agent_thought ? `<div class="step-thought">"${escapeHtml(s.agent_thought)}"</div>` : ''}
      ${s.tool_args ? `<div style="font-family:var(--font-mono); font-size:11px; color:var(--text-dim); margin-bottom:4px;">Args: ${escapeHtml(JSON.stringify(s.tool_args))}</div>` : ''}
      ${s.tool_output ? `<div class="code-box" style="margin-top:4px; max-height:140px;">${escapeHtml(s.tool_output)}</div>` : ''}
    </div>
  `).join('');
}

async function generateRegressionTest() {
  if (!lastTrace) return;
  const btn = document.getElementById('btn-generate-test');
  btn.disabled = true;
  btn.textContent = 'Generating & Validating...';

  const msgBox = document.getElementById('generate-message');
  msgBox.style.display = 'block';
  msgBox.style.color = 'var(--accent)';
  msgBox.textContent = 'Running dual ground-truth validation (Negative on failure snapshot + Positive on corrected state)...';

  try {
    const res = await fetch('/api/generate-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trace_data: lastTrace })
    });

    const data = await res.json();
    if (data.validated) {
      msgBox.innerHTML = `<strong>SUCCESS:</strong> ${escapeHtml(data.message)}<br><span style="color:var(--text-dim); font-size:11px;">Saved to: ${data.task.id}.yaml</span>`;
      await loadTasks();
    } else {
      msgBox.style.color = 'var(--red)';
      msgBox.textContent = 'Validation Failed: ' + data.message;
    }
  } catch (e) {
    msgBox.style.color = 'var(--red)';
    msgBox.textContent = 'Generation Error: ' + e;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Regression Test';
  }
}

async function compareModels() {
  if (!selectedTask) return;
  const btn = document.getElementById('btn-compare');
  btn.disabled = true;
  btn.textContent = 'Comparing...';

  const backend = document.getElementById('backend-select').value;

  try {
    const res = await fetch('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_file: selectedTask.file_path,
        models: ['mock-buggy', 'mock-fixed'],
        backend: backend
      })
    });

    const data = await res.json();
    renderCompareResults(data.traces);
  } catch (e) {
    alert('Comparison error: ' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Compare Models';
  }
}

function renderCompareResults(traces) {
  const panel = document.getElementById('compare-panel');
  panel.style.display = 'block';

  const container = document.getElementById('compare-container');
  let rows = traces.map(t => {
    const passed = (t.status === 'PASSED');
    const failedInvs = t.invariant_results.filter(r => !r.passed).map(r => r.spec.key_path || r.spec.path || r.spec.command).join(', ') || 'None';
    return `
      <tr>
        <td><strong>${escapeHtml(t.model_name)}</strong></td>
        <td><span class="badge-status ${passed ? 'pass' : 'fail'}">${t.status}</span></td>
        <td>${t.duration_seconds.toFixed(2)}s</td>
        <td>${t.steps.length}</td>
        <td style="color:${failedInvs !== 'None' ? 'var(--red)' : 'var(--accent)'}">${escapeHtml(failedInvs)}</td>
      </tr>
    `;
  }).join('');

  container.innerHTML = `
    <table class="compare-table">
      <thead>
        <tr>
          <th>Model</th>
          <th>Status</th>
          <th>Duration</th>
          <th>Steps</th>
          <th>Failed Invariants</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function runE2BDemo() {
  const e2bTask = tasks.find(t => t.id.includes('e2b'));
  if (e2bTask) {
    selectTask(e2bTask);
    document.getElementById('backend-select').value = 'e2b';
    document.getElementById('model-select').value = 'mock-fixed';
    runCurrentTask();
  } else {
    alert('E2B demo task not found in task list.');
  }
}

function escapeHtml(str) {
  if (typeof str !== 'string') return String(str);
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  initCustomCursor();
  initMatrixRain();
  loadSystemStatus();
  loadTasks();

  document.getElementById('btn-run').addEventListener('click', runCurrentTask);
  document.getElementById('btn-compare').addEventListener('click', compareModels);
  document.getElementById('btn-generate-test').addEventListener('click', generateRegressionTest);
  document.getElementById('btn-demo-e2b').addEventListener('click', runE2BDemo);
});
