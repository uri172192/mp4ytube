let csrf = '', timer = null;
const error = document.querySelector('#error');
const prepare = document.querySelector('#prepare');
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify(body)});
  if (response.status === 401) { location.replace('/'); throw new Error('La sessió ha caducat.'); }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'No s’ha pogut completar l’operació.');
  return data;
}
function show(job) {
  document.querySelector('#job').hidden = false;
  document.querySelector('#message').textContent = job.filename || job.message;
  document.querySelector('#progress').value = job.progress;
  const active = job.state === 'queued' || job.state === 'downloading';
  prepare.disabled = active;
  const save = document.querySelector('#save');
  save.hidden = job.state !== 'ready';
  if (job.state === 'ready') save.href = `/api/jobs/${encodeURIComponent(job.id)}/download`;
  if (active) {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try { show(await api(`/api/jobs/${encodeURIComponent(job.id)}`)); }
      catch (err) { error.textContent = err.message; prepare.disabled = false; }
    }, 2000);
  }
}
document.querySelector('#download').addEventListener('submit', async event => {
  event.preventDefault(); error.textContent = ''; prepare.disabled = true;
  try { show(await api('/api/jobs', {url:document.querySelector('#url').value.trim(), height:Number(document.querySelector('#height').value)})); }
  catch (err) { error.textContent = err.message; prepare.disabled = false; }
});
document.querySelector('#logout').addEventListener('click', async () => {
  try { await api('/api/logout', {}); location.replace('/'); }
  catch (err) { error.textContent = err.message; }
});
(async () => {
  try {
    const data = await api('/api/session'); csrf = data.csrf;
    if (data.jobs.length) show(data.jobs.find(j => ['queued','downloading'].includes(j.state)) || data.jobs[data.jobs.length - 1]);
  } catch (err) { error.textContent = err.message; }
})();
