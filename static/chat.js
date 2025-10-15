document.addEventListener('DOMContentLoaded', () => {
  const sendBtn = document.getElementById('sendBtn');
  const symptoms = document.getElementById('symptoms');
  const messages = document.getElementById('messages');
  const chatId = messages && messages.dataset ? messages.dataset.chatId : null;
  const username = localStorage.getItem('health_username') || '';
  if (!sendBtn || !symptoms || !messages || !chatId) return;

  // toggle typing class while the user types
  symptoms.addEventListener('input', ()=>{
    if (symptoms.value && symptoms.value.trim().length>0) symptoms.classList.add('typing')
    else symptoms.classList.remove('typing')
  })

  sendBtn.addEventListener('click', async () => {
    const text = symptoms.value.trim();
    if (!text) return;
    // append user message locally
    const userDiv = document.createElement('div');
    userDiv.className = 'message user';
    userDiv.textContent = 'user: ' + text;
    messages.appendChild(userDiv);

    sendBtn.disabled = true;
    try {
      const res = await fetch(`/api/chats/${chatId}/message`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      const body = await res.json();

      // If server returned parsed JSON, render a structured card
      if (body.parsed) {
  const card = document.createElement('div');
  card.className = 'assistant-card';

        const pc = body.parsed.possible_conditions || body.parsed.possibleConditions || [];
        const recs = body.parsed.recommendations || body.parsed.recommendations || [];
        const disc = body.parsed.disclaimer || body.parsed.disclaimer || '';

  const pcEl = document.createElement('div');
  pcEl.innerHTML = '<strong>Possible conditions</strong>';
        const ul = document.createElement('ul');
        pc.forEach(p => {
          const li = document.createElement('li');
          if (typeof p === 'string') {
            li.textContent = p;
          } else {
            li.textContent = p.name + (p.reason ? ': ' + p.reason : '');
          }
          ul.appendChild(li);
        });
        pcEl.appendChild(ul);
        card.appendChild(pcEl);

        if (recs.length) {
          const rEl = document.createElement('div');
          rEl.innerHTML = '<strong>Recommendations</strong>';
          const rul = document.createElement('ul');
          recs.forEach(r => {
            const li = document.createElement('li');
            li.textContent = r;
            rul.appendChild(li);
          });
          rEl.appendChild(rul);
          card.appendChild(rEl);
        }

        if (disc) {
          const dEl = document.createElement('div');
          dEl.className = 'disclaimer';
          dEl.textContent = 'Disclaimer: ' + disc;
          card.appendChild(dEl);
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'message assistant';
        wrapper.appendChild(card);
        messages.appendChild(wrapper);
        // clear composer and remove typing style
        symptoms.value = '';
        symptoms.classList.remove('typing');
      } else {
        const aDiv = document.createElement('div');
        const nameLabel = username ? `${username},` : 'Assistant';
        aDiv.className = 'message assistant';
        aDiv.textContent = `${nameLabel} ${body.assistant || body.error || 'No response'}`;
        messages.appendChild(aDiv);
      }
      } catch (err) {
      const aDiv = document.createElement('div');
      aDiv.className = 'message assistant';
      aDiv.textContent = 'Assistant error: ' + err.message;
      messages.appendChild(aDiv);
    } finally {
      sendBtn.disabled = false;
    }
  });
});
