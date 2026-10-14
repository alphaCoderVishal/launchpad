'use strict';
let token = '', selected = '', timeline = '', operator = false, loading = false;
let identityVersion = 0;
const $ = id => document.getElementById(id);
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function notice(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; }
function resetDetail() { timeline = ''; $('timeline-id').textContent = 'Select a deployment'; $('events').textContent = 'Select a deployment to inspect its timeline.'; $('response').textContent = 'No workload response yet.'; }
async function api(path, method = 'GET', body, key) {
  const headers = {Authorization: `Bearer ${token}`};
  if (body) headers['Content-Type'] = 'application/json';
  if (key) headers['Idempotency-Key'] = key;
  const response = await fetch(`/api${path}`, {method, headers, body: body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.title || `Request failed (${response.status})`);
  return result;
}
async function refresh() {
  if (!token || loading) return;
  loading = true;
  const version = identityVersion;
  try {
    const services = await api('/services');
    if (version !== identityVersion) return;
    $('service-count').textContent = services.length;
    if (!services.some(s => s.name === selected)) selected = services[0]?.name || '';
    $('services').innerHTML = services.length ? services.map(s => `<button class="service ${selected === s.name ? 'selected' : ''}" data-service="${escapeText(s.name)}"><strong>${escapeText(s.name)} <span class="release">${escapeText(s.activeRelease || '—')}</span></strong><small>${escapeText(s.owner)} · ${s.activeRelease ? 'Active workload' : 'Awaiting first release'}</small></button>`).join('') : '<div class="empty">Register your first service to deploy a workload.</div>';
    $('deploy-button').disabled = !selected; $('probe').disabled = !selected;
    if (selected) {
      const s = services.find(s => s.name === selected);
      $('selected-title').textContent = selected; $('active-release').textContent = s.activeRelease || 'NO ACTIVE RELEASE';
      const deployments = await api(`/services/${selected}/deployments`);
      if (version !== identityVersion) return;
      $('deployments').innerHTML = deployments.length ? deployments.map(d => `<div class="deployment"><div class="meta">${escapeText(d.release)} <span class="status ${d.status}">${d.status.replaceAll('_',' ')}</span><small>${escapeText(d.environment)} · ${escapeText(d.id.slice(0,8))} · ${new Date(d.createdAt).toLocaleTimeString()}</small></div><div><button class="secondary" data-events="${d.id}">Timeline</button>${d.status === 'WAITING_APPROVAL' && operator ? `<button data-approve="${d.id}">Approve</button>` : ''}${['QUEUED','WAITING_APPROVAL'].includes(d.status) ? `<button class="secondary" data-cancel="${d.id}">Cancel</button>` : ''}</div></div>`).join('') : '<div class="empty">No deployments yet. Start with v1.</div>';
    }
    if (timeline) await showEvents(timeline);
  } catch (error) { notice(error.message, true); }
  finally { loading = false; }
}
async function showEvents(id) {
  const version = identityVersion, service = selected;
  timeline = id;
  const events = await api(`/deployments/${id}/events`);
  if (version !== identityVersion || service !== selected || timeline !== id) return;
  $('timeline-id').textContent = id.slice(0,8);
  $('events').innerHTML = events.map(e => `<div class="event"><time>${new Date(e.createdAt).toLocaleString()}</time><strong>${escapeText(e.type)}</strong><span>${escapeText(e.detail)} <small>· ${escapeText(e.actor)}</small></span></div>`).join('');
}
$('connect').addEventListener('submit', async e => {
  e.preventDefault(); token = $('token').value.trim(); selected = ''; identityVersion++; resetDetail(); pending = null;
  $('services').textContent = 'Connecting…'; $('service-count').textContent = '—'; $('deployments').textContent = 'Select a service to inspect its releases.';
  $('selected-title').textContent = 'Release workspace'; $('active-release').textContent = 'NO SERVICE'; $('deploy-button').disabled = true; $('probe').disabled = true;
  try { const me = await api('/me'); operator = me.operator; $('identity').textContent = `${me.name} · ${operator ? 'Operator' : 'Developer'}`; $('token').value = ''; notice('Workspace connected.'); await refresh(); }
  catch (error) { token = ''; $('identity').textContent = ''; $('services').textContent = 'Connect with a valid token to view services.'; notice(error.message, true); }
});
$('register').addEventListener('submit', async e => {
  e.preventDefault();
  try { const s = await api('/services', 'POST', {name:$('service-name').value.trim()}); selected = s.name; resetDetail(); $('service-name').value = ''; notice('Service registered.'); await refresh(); }
  catch (error) { notice(error.message, true); }
});
$('deploy').addEventListener('submit', async e => {
  e.preventDefault(); if (!selected) return;
  // Keep the same key for retries of this exact intent after an ambiguous network failure.
  const intent = JSON.stringify([selected,$('release').value,$('environment').value]);
  if (!pending || pending.intent !== intent) pending = {intent,key:crypto.randomUUID()};
  $('deploy-button').disabled = true;
  try { const d = await api(`/services/${selected}/deployments`,'POST',{release:$('release').value,environment:$('environment').value},pending.key); pending = null; timeline = d.id; notice('Deployment accepted. Follow its audit timeline below.'); await refresh(); }
  catch (error) { notice(error.message, true); }
  finally { $('deploy-button').disabled = !selected; }
});
let pending = null;
$('services').addEventListener('click', async e => { const button = e.target.closest('[data-service]'); if (button) { selected = button.dataset.service; resetDetail(); await refresh(); } });
$('deployments').addEventListener('click', async e => {
  const button = e.target.closest('button'); if (!button) return;
  try {
    if (button.dataset.events) await showEvents(button.dataset.events);
    if (button.dataset.approve) { await api(`/deployments/${button.dataset.approve}/approve`,'POST'); notice('Operator approval recorded.'); await refresh(); }
    if (button.dataset.cancel) { await api(`/deployments/${button.dataset.cancel}/cancel`,'POST'); notice('Deployment cancelled.'); await refresh(); }
  } catch (error) { notice(error.message, true); }
});
$('probe').addEventListener('click', async () => { try { $('response').textContent = JSON.stringify(await api(`/services/${selected}/response`),null,2); } catch (error) { notice(error.message,true); } });
setInterval(refresh,3000);
