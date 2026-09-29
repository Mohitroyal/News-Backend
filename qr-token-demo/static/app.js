const $ = id => document.getElementById(id);
const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
async function api(url, options = {}) {
  const response = await fetch(url, {cache: 'no-store', ...options,
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf(), ...options.headers}});
  const data = await response.json().catch(() => ({error: `Request failed (${response.status}).`}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
function message(id, text, error = false) {$(id).textContent = text; $(id).classList.toggle('error', error);}
function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16)); b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
  const s = [...b].map(x => x.toString(16).padStart(2, '0')).join('');
  return `${s.slice(0,8)}-${s.slice(8,12)}-${s.slice(12,16)}-${s.slice(16,20)}-${s.slice(20)}`;
}
async function initHome() {
  $('token_number').value = `DEMO-${Date.now()}`;
  let pending = JSON.parse(sessionStorage.getItem('pending-token') || 'null');
  if (pending) for (const field of ['token_number','project','facility']) $(field).value = pending[field];
  async function refresh() {
    try {
      const data = await api('/api/tokens/'); $('token-list').replaceChildren();
      if (!data.tokens.length) $('token-list').textContent = 'No tokens yet. Create your first sample above.';
      for (const token of data.tokens) {
        const row = document.createElement('div'); row.className = 'token-row';
        const link = document.createElement('a'); link.href = token.detail_url; link.textContent = token.token_number + ' ↗';
        const date = document.createElement('small'); date.textContent = new Date(token.created_at).toLocaleString();
        const manage = document.createElement('a'); manage.href = token.detail_url + 'manage/'; manage.textContent = 'Edit demo status'; manage.className='secondary';
        row.append(link, date, manage); $('token-list').append(row);
      }
    } catch (e) { $('token-list').textContent = e.message; }
  }
  $('refresh-list').onclick = refresh;
  $('create-form').onsubmit = async event => {
    event.preventDefault();
    const input = Object.fromEntries(['token_number','project','facility'].map(f => [f, $(f).value.trim()]));
    if (!pending || Object.keys(input).some(k => input[k] !== pending[k])) pending = {...input, request_id: uuid()};
    sessionStorage.setItem('pending-token', JSON.stringify(pending));
    $('create-button').disabled = true; message('create-message','Saving workbook and generating QR…');
    try {
      const token = await api('/api/tokens/', {method:'POST', body:JSON.stringify(pending)});
      $('empty-qr').hidden = true; $('created').hidden = false; $('qr-image').src = token.qr_image_url;
      $('created-number').textContent = token.token_number; $('open-token').href = token.detail_url;
      $('download-excel').href = token.workbook_url; $('download-qr').href = token.qr_image_url;
      $('qr-target').textContent = token.qr_url;
      message('create-message','Created. Your Excel workbook and QR are ready.');
      pending = null; sessionStorage.removeItem('pending-token');
      $('token_number').value = `DEMO-${Date.now()}`; await refresh();
    } catch (e) {message('create-message',e.message, true);}
    finally {$('create-button').disabled = false;}
  };
  $('lookup-button').onclick = () => {
    const value = $('lookup').value.trim();
    const pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    let id = value;
    if (!pattern.test(id)) {
      try {const url = new URL(value); if (url.origin !== location.origin) throw Error();
        id = url.pathname.match(/^\/tokens\/([^/]+)\/?$/)?.[1] || '';
      } catch {id = '';}
    }
    if (!pattern.test(id)) return message('lookup-message','Paste a token UUID or a link from this server.',true);
    location.href = `/tokens/${id}/`;
  };
  await refresh();
}
async function initDetail(id) {
  let selected = 'Token Summary';
  function showSheet(sheet) {
    selected = sheet.name; $('sheet-title').textContent = sheet.title;
    for (const button of $('sheet-tabs').children) {button.classList.toggle('active',button.textContent === selected); button.setAttribute('aria-selected',button.textContent === selected);}
    const head = document.createElement('thead'), body = document.createElement('tbody'), heading = document.createElement('tr');
    for (const text of sheet.headers) {const th = document.createElement('th');th.textContent = text ?? '';heading.append(th);}
    head.append(heading);
    for (const row of sheet.rows) {const tr = document.createElement('tr');for (const value of row) {const td = document.createElement('td');td.textContent = value ?? '—';tr.append(td);}body.append(tr);}
    $('sheet-table').replaceChildren(head,body);
  }
  function render(data) {
    $('detail-title').textContent = data.summary['Token ID']; $('detail-project').textContent = data.summary.Project;
    $('output').textContent = data.summary['Biochar output'] + ' kg';
    $('removal').textContent = Number(data.summary['Net token removal']).toFixed(2) + ' kg CO₂e';
    $('status').textContent = data.summary['Verification status'];
    $('verification').value = data.summary['Verification status'];
    $('detail-qr').src = data.qr_image_url; $('detail-excel').href = data.workbook_url;
    $('detail-qr-save').href = data.qr_image_url; $('detail-url').textContent = data.qr_url;
    $('sheet-tabs').replaceChildren();
    for (const sheet of data.sheets) {const button = document.createElement('button');button.textContent = sheet.name;button.setAttribute('role','tab');button.onclick=()=>showSheet(sheet);$('sheet-tabs').append(button);}
    showSheet(data.sheets.find(s => s.name === selected) || data.sheets[0]);
  }
  async function reload() {try {render(await api(`/api/tokens/${id}/`)); message('detail-error','');} catch(e) {message('detail-error',e.message,true);}}
  $('reload-record').onclick = reload;
  $('update-form').onsubmit = async event => {event.preventDefault();$('update-button').disabled = true;
    try {render(await api(`/api/tokens/${id}/`,{method:'PATCH',body:JSON.stringify({verification_status:$('verification').value})}));message('update-message','Excel updated. Your QR is unchanged.');}
    catch(e) {message('update-message',e.message,true);} finally {$('update-button').disabled=false;}
  };
  await reload();
}
