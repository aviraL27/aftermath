// Aftermath Dashboard Client Application

let tasks = [];
let selectedTask = null;
let lastTrace = null;

async function loadSystemStatus() {
  try {
    const res = await fetch('/api/system-status');
    const data = await res.json();
    const gemmaPill = document.getElementById('status-gemma');
    const mistralPill = document.getElementById('status-mistral');
    if (gemmaPill) {
      gemmaPill.textContent = `Gemma 4: Google API (2.4s) / Ollama Fallback`;
    }
    if (mistralPill) {
      mistralPill.textContent = `Mistral: ${data.mistral_model} (Apache-2.0)`;
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
    if (tasks.length > 0 && !selectedTask) {
      selectTask(tasks[0]);
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

  container.innerHTML = tasks.map(t => `
    <div class="task-card ${selectedTask && selectedTask.id === t.id ? 'selected' : ''}" onclick="window.onSelectTask('${t.id}')">
      <div class="task-card-title">${escapeHtml(t.name)}</div>
      <div class="task-card-meta">
        <span>${t.is_regression_test ? '<span style="color:var(--accent-solar);">Regression</span>' : 'Standard'}</span>
        <span>${t.invariants_count} Invariants</span>
      </div>
    </div>
  `).join('');
}

window.onSelectTask = function(taskId) {
  const t = tasks.find(x => x.id === taskId);
  if (t) selectTask(t);
};

function selectTask(task) {
  selectedTask = task;
  renderTaskList();

  document.getElementById('active-task-name').textContent = task.name;
  document.getElementById('active-task-desc').textContent = task.description || 'Task ready to run.';
  document.getElementById('active-task-instruction').textContent = task.description || 'Updating workspace...';

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
  btn.textContent = 'Executing Agent...';

  const model = document.getElementById('model-select').value;

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_file: selectedTask.file_path,
        model: model
      })
    });

    const trace = await res.json();
    lastTrace = trace;
    renderRunResults(trace);
  } catch (e) {
    alert('Execution error: ' + e);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Execute Task';
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
    const key = a.spec.key_path || a.spec.path;
    items.push(`
      <div class="assertion-item ${passed ? 'passed' : 'failed'}">
        <div>
          <span style="color:var(--text-muted); font-size:10px; margin-right:8px;">ASSERTION</span>
          <strong>${escapeHtml(key)}</strong>
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
    const key = inv.spec.key_path || inv.spec.path;
    items.push(`
      <div class="assertion-item ${passed ? 'passed' : 'failed'}">
        <div>
          <span style="color:var(--accent-solar); font-size:10px; margin-right:8px;">INVARIANT</span>
          <strong>${escapeHtml(key)}</strong>
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
        ${s.tool_name ? `<span class="step-tool">Tool: ${s.tool_name}</span>` : '<span style="color:var(--text-muted);">Finish</span>'}
        <span style="color:var(--text-muted); font-size:11px; margin-left:auto;">${s.duration_seconds.toFixed(2)}s</span>
      </div>
      ${s.agent_thought ? `<div class="step-thought">"${escapeHtml(s.agent_thought)}"</div>` : ''}
      ${s.tool_args ? `<div style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary); margin-bottom:4px;">Args: ${escapeHtml(JSON.stringify(s.tool_args))}</div>` : ''}
      ${s.tool_output ? `<div class="code-box" style="margin-top:4px; max-height:120px;">${escapeHtml(s.tool_output)}</div>` : ''}
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
  msgBox.style.color = 'var(--text-secondary)';
  msgBox.textContent = 'Running double-validation against failing state and known-correct state...';

  try {
    const res = await fetch('/api/generate-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trace_data: lastTrace })
    });

    const data = await res.json();
    if (data.validated) {
      msgBox.style.color = 'var(--status-pass)';
      msgBox.innerHTML = `<strong>Validated:</strong> ${escapeHtml(data.message)}`;
      // Refresh task list so new regression test appears in sidebar
      await loadTasks();
    } else {
      msgBox.style.color = 'var(--status-fail)';
      msgBox.innerHTML = `<strong>Validation Failed:</strong> ${escapeHtml(data.message)}`;
    }
  } catch (e) {
    msgBox.style.color = 'var(--status-fail)';
    msgBox.textContent = 'Error: ' + e;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Regression Test';
  }
}

async function runComparison() {
  if (!selectedTask) return;
  const btn = document.getElementById('btn-compare');
  btn.disabled = true;
  btn.textContent = 'Comparing Models...';

  const panel = document.getElementById('compare-panel');
  panel.style.display = 'block';
  const container = document.getElementById('compare-container');
  container.innerHTML = '<div style="color:var(--text-secondary); font-size:12px;">Running benchmark across Gemma 4 and Mistral...</div>';

  try {
    const res = await fetch('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_file: selectedTask.file_path,
        models: ['gemma4', 'mistral']
      })
    });

    const data = await res.json();
    const traces = data.traces || [];

    let html = `
      <table style="width:100%; border-collapse:collapse; font-size:12px; font-family:var(--font-mono);">
        <thead>
          <tr style="border-bottom:1px solid var(--border-whisper); text-align:left; color:var(--text-muted);">
            <th style="padding:8px;">Model</th>
            <th style="padding:8px;">Provider</th>
            <th style="padding:8px;">Status</th>
            <th style="padding:8px;">Duration</th>
            <th style="padding:8px;">Steps</th>
            <th style="padding:8px;">Diff Lines</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const t of traces) {
      const pass = t.status === 'PASSED';
      const diffLines = t.workspace_diff ? t.workspace_diff.split('\n').length : 0;
      html += `
        <tr style="border-bottom:1px solid var(--border-whisper);">
          <td style="padding:8px; font-weight:600; color:var(--text-primary);">${t.model_name}</td>
          <td style="padding:8px; color:var(--text-secondary);">${t.provider}</td>
          <td style="padding:8px;"><span class="badge-status ${pass ? 'pass' : 'fail'}">${t.status}</span></td>
          <td style="padding:8px;">${t.duration_seconds.toFixed(2)}s</td>
          <td style="padding:8px;">${t.steps.length}</td>
          <td style="padding:8px;">${diffLines}</td>
        </tr>
      `;
    }

    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<div style="color:var(--status-fail);">Comparison failed: ${escapeHtml(String(e))}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Cross-Model Compare';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
  loadSystemStatus();
  loadTasks();

  document.getElementById('btn-run').addEventListener('click', runCurrentTask);
  document.getElementById('btn-generate-test').addEventListener('click', generateRegressionTest);
  document.getElementById('btn-compare').addEventListener('click', runComparison);
});

