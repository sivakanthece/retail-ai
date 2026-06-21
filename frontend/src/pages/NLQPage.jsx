import React, { useState, useEffect, useRef } from 'react';
import { nlqAPI } from '../services/api';

export default function NLQPage() {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Hi! I\'m your Retail AI assistant powered by GPT-4o / Gemini / Groq. Ask me anything about your inventory.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const bottomRef = useRef();

  useEffect(() => {
    nlqAPI.suggestions().then(r => setSuggestions(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (query) => {
    const q = (query || input).trim();
    if (!q) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const res = await nlqAPI.query(q);
      setMessages(prev => [...prev, { role: 'ai', text: res.data.answer }]);
    } catch (e) {
      const msg = e.response?.data?.detail || 'Failed to get response. Check that an LLM API key (GROQ_API_KEY / OPENAI_API_KEY) is configured.';
      setMessages(prev => [...prev, { role: 'ai', text: `⚠️ ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-title">🤖 AI Natural Language Query</div>
      <div style={{ fontSize: 13, color: '#888', marginBottom: 16 }}>
        Powered by{' '}
        <span style={{ background: '#dcfce7', color: '#15803d', borderRadius: 4, padding: '1px 7px', fontWeight: 600, fontSize: 12 }}>GPT-4o</span>
        {' '}·{' '}
        <span style={{ background: '#cffafe', color: '#0e7490', borderRadius: 4, padding: '1px 7px', fontWeight: 600, fontSize: 12 }}>Gemini</span>
        {' '}·{' '}
        <span style={{ background: '#ede9fe', color: '#6d28d9', borderRadius: 4, padding: '1px 7px', fontWeight: 600, fontSize: 12 }}>Groq Llama</span>
        {' '}— automatic fallback chain, uses whichever key is configured.
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="chat-container">
          <div className="chat-messages" style={{ background: '#fafbff' }}>
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}`}>{m.text}</div>
            ))}
            {loading && <div className="chat-bubble ai" style={{ opacity: 0.6 }}>⏳ Thinking...</div>}
            <div ref={bottomRef} />
          </div>
          <div className="chat-input-row">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !loading && send()}
              placeholder="Ask about inventory, stock levels, alerts..."
              disabled={loading}
            />
            <button className="btn btn-primary" onClick={() => send()} disabled={loading || !input.trim()}>Send</button>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">💡 Suggested Queries</div>
        <div>
          {suggestions.map((s, i) => (
            <span key={i} className="suggestion-chip" onClick={() => send(s)}>{s}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
