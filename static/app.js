// static/app.js
async function fetchHistory(){
  try{
    const res = await fetch('/api/history');
    const j = await res.json();
    const container = document.getElementById('history');
    container.innerHTML = '';
    j.forEach(h=>{
      const d = document.createElement('div');
      d.className = 'card';
      d.innerHTML = `<div><strong>Q:</strong> ${escapeHtml(h.prompt)}</div>
                     <div style="margin-top:8px;white-space:pre-wrap"><strong>A:</strong> ${escapeHtml(h.response)}</div>
                     <div class="meta">${new Date(h.created_at).toLocaleString()}</div>`;
      container.appendChild(d);
    });
  }catch(e){
    console.error(e);
  }
}
function escapeHtml(s){ if(!s) return ''; return s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'); }

document.getElementById('ask-form').addEventListener('submit', async function(e){
  e.preventDefault();
  const prompt = document.getElementById('prompt').value;
  if(!prompt.trim()) return alert('Prompt likho pehle');
  const btn = document.getElementById('submit-btn');
  btn.disabled = true; btn.textContent = 'Soch raha hai...';
  try{
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({prompt})
    });
    if(!res.ok){
      const err = await res.json().catch(()=>({detail:'Server error'}));
      alert('Error: '+(err.detail||res.statusText));
    } else {
      document.getElementById('prompt').value = '';
      await fetchHistory();
    }
  }catch(err){
    console.error(err); alert('Network error');
  } finally {
    btn.disabled = false; btn.textContent = 'Poochho';
  }
});

window.addEventListener('load', fetchHistory);
