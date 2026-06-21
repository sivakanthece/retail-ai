import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Detection from './pages/Detection';
import InventoryPage from './pages/InventoryPage';
import NLQPage from './pages/NLQPage';
import AlertsPage from './pages/AlertsPage';
import ProductLibrary from './pages/ProductLibrary';
import Login from './pages/Login';

const STYLES = `
  .app { display: flex; height: 100vh; }
  .sidebar { width: 220px; background: #1a237e; color: white; display: flex; flex-direction: column; padding: 0; flex-shrink: 0; }
  .sidebar-brand { padding: 20px 16px; font-size: 14px; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,0.1); line-height: 1.4; }
  .sidebar-brand span { display: block; font-size: 11px; font-weight: 400; opacity: 0.7; margin-top: 2px; }
  .sidebar nav { flex: 1; padding: 12px 0; }
  .sidebar nav a { display: flex; align-items: center; gap: 10px; padding: 11px 16px; color: rgba(255,255,255,0.75); text-decoration: none; font-size: 14px; transition: all 0.15s; }
  .sidebar nav a:hover, .sidebar nav a.active { background: rgba(255,255,255,0.12); color: white; }
  .sidebar-user { padding: 14px 16px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 12px; display: flex; justify-content: space-between; align-items: center; }
  .logout-btn { background: rgba(255,255,255,0.15); border: none; color: white; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 11px; }
  .main { flex: 1; overflow-y: auto; background: #f0f2f5; }
  .page { padding: 28px; max-width: 1200px; }
  .page-title { font-size: 22px; font-weight: 700; color: #1a237e; margin-bottom: 20px; }
  .card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 20px; }
  .card-title { font-size: 15px; font-weight: 600; color: #333; margin-bottom: 14px; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 20px; }
  .stat-card { background: white; border-radius: 10px; padding: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .stat-label { font-size: 12px; color: #888; margin-bottom: 6px; }
  .stat-value { font-size: 28px; font-weight: 700; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge-red { background: #fde8e8; color: #c53030; }
  .badge-green { background: #e6f4ea; color: #1e7e34; }
  .badge-orange { background: #fff3e0; color: #e65100; }
  .btn { padding: 9px 18px; border-radius: 6px; border: none; cursor: pointer; font-size: 14px; font-weight: 500; transition: opacity 0.15s; }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: #1a237e; color: white; }
  .btn-danger { background: #e53935; color: white; }
  .btn-sm { padding: 5px 12px; font-size: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th { text-align: left; padding: 10px 12px; background: #f5f6fa; color: #555; font-weight: 600; font-size: 12px; border-bottom: 1px solid #e8e8e8; }
  td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; color: #333; }
  tr:hover td { background: #fafbff; }
  input, select, textarea { width: 100%; padding: 9px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; outline: none; }
  input:focus, select:focus, textarea:focus { border-color: #1a237e; box-shadow: 0 0 0 2px rgba(26,35,126,0.1); }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .form-group { display: flex; flex-direction: column; gap: 5px; margin-bottom: 14px; }
  .form-group label { font-size: 12px; font-weight: 600; color: #555; }
  .alert-item { display: flex; gap: 12px; align-items: flex-start; padding: 12px; border-radius: 8px; background: #fff8e1; border-left: 4px solid #ffa000; margin-bottom: 10px; }
  .alert-unread { background: #fff8e1; }
  .alert-read { background: #f9f9f9; border-left-color: #ccc; opacity: 0.7; }
  .chat-container { display: flex; flex-direction: column; height: 480px; }
  .chat-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
  .chat-bubble { max-width: 80%; padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.5; }
  .chat-bubble.user { align-self: flex-end; background: #1a237e; color: white; border-bottom-right-radius: 4px; }
  .chat-bubble.ai { align-self: flex-start; background: #f0f2f5; color: #333; border-bottom-left-radius: 4px; white-space: pre-wrap; }
  .chat-input-row { display: flex; gap: 10px; padding: 12px 14px; border-top: 1px solid #eee; }
  .chat-input-row input { flex: 1; }
  .drop-zone { border: 2px dashed #b0bec5; border-radius: 12px; padding: 40px; text-align: center; cursor: pointer; transition: all 0.2s; color: #666; }
  .drop-zone:hover, .drop-zone.over { border-color: #1a237e; background: #f0f2f5; color: #1a237e; }
  .detection-result { margin-top: 14px; }
  .detection-box { background: #e8f5e9; border-radius: 8px; padding: 14px; margin-top: 10px; }
  .error { color: #c53030; font-size: 13px; margin-top: 6px; }
  .loading { color: #888; font-size: 13px; }
  .suggestion-chip { display: inline-block; margin: 4px; padding: 6px 12px; background: #e8eaf6; border-radius: 20px; font-size: 13px; cursor: pointer; transition: background 0.15s; }
  .suggestion-chip:hover { background: #c5cae9; }
`;

function Sidebar({ user, onLogout }) {
  const navItems = [
    { path: '/', label: '📊 Dashboard' },
    { path: '/detection', label: '🔍 Detection' },
    { path: '/library',   label: '🏪 Product Library' },
    { path: '/inventory', label: '📦 Inventory' },
    { path: '/nlq', label: '🤖 AI Query' },
    { path: '/alerts', label: '🔔 Alerts' },
  ];
  return (
    <div className="sidebar">
      <div className="sidebar-brand">
        Retail AI System
        <span>Inventory Intelligence</span>
      </div>
      <nav>
        {navItems.map(item => (
          <NavLink key={item.path} to={item.path} end={item.path === '/'} className={({ isActive }) => isActive ? 'active' : ''}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-user">
        <span>👤 {user?.username} <span style={{ opacity: 0.6 }}>({user?.role})</span></span>
        <button className="logout-btn" onClick={onLogout}>Logout</button>
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')); } catch { return null; }
  });

  const handleLogin = (userData) => {
    localStorage.setItem('token', userData.access_token);
    localStorage.setItem('user', JSON.stringify({ username: userData.username, role: userData.role }));
    setUser({ username: userData.username, role: userData.role });
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  };

  return (
    <>
      <style>{STYLES}</style>
      <BrowserRouter>
        {!user ? (
          <Login onLogin={handleLogin} />
        ) : (
          <div className="app">
            <Sidebar user={user} onLogout={handleLogout} />
            <div className="main">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/detection" element={<Detection />} />
                <Route path="/library"   element={<ProductLibrary />} />
                <Route path="/inventory" element={<InventoryPage user={user} />} />
                <Route path="/nlq" element={<NLQPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="*" element={<Navigate to="/" />} />
              </Routes>
            </div>
          </div>
        )}
      </BrowserRouter>
    </>
  );
}
