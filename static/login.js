document.querySelector('#login').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  const error = document.querySelector('#error');
  button.disabled = true; error.textContent = '';
  try {
    const response = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:document.querySelector('#password').value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No s’ha pogut iniciar sessió.');
    location.replace('/');
  } catch (err) { error.textContent = err.message; }
  finally { button.disabled = false; }
});
