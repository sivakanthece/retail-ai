import React, { useState } from 'react';
import { authAPI } from '../services/api';

const S = `
  .login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a237e 0%, #283593 100%); }
  .login-card { background: white; border-radius: 16px; padding: 40px; width: 380px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
  .login-title { font-size: 22px; font-weight: 700; color: #1a237e; margin-bottom: 4px; }
  .login-sub { font-size: 13px; color: #888; margin-bottom: 28px; }
  .login-hint { background: #f0f2f5; border-radius: 8px; padding: 12px; font-size: 12px; color: #555; margin-top: 20px; line-height: 1.8; }
  .login-btn { width: 100%; padding: 11px; background: #1a237e; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 4px; }
  .login-btn:hover { background: #283593; }
  .login-error { color: #c53030; font-size: 13px; margin-top: 8px; text-align: center; }
  .login-group { margin-bottom: 16px; }
  .login-group label { display: block; font-size: 12px; font-weight: 600; color: #555; margin-bottom: 5px; }
  .login-group input { width: 100%; padding: 10px 12px; border: 1px solid #d9d9d9; border-radius: 8px; font-size: 14px; outline: none; }
  .login-group input:focus { border-color: #1a237e; }
`;

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await authAPI.login(username, password);
      onLogin(res.data);
    } catch {
      setError('Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{S}</style>
      <div className="login-wrap">
        <div className="login-card">
          <div className="login-title">🛒 Retail AI System</div>
          <div className="login-sub">Intelligent Inventory Management</div>
          <form onSubmit={handleSubmit}>
            <div className="login-group">
              <label>Username</label>
              <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Enter username" required />
            </div>
            <div className="login-group">
              <label>Password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter password" required />
            </div>
            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            {error && <div className="login-error">{error}</div>}
          </form>
          <div className="login-hint">
            <strong>Demo accounts:</strong><br />
            admin / admin123 (full access)<br />
            manager / manager123<br />
            analyst / analyst123
          </div>
        </div>
      </div>
    </>
  );
}
