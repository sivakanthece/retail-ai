import React, { useEffect, useState } from 'react';
import { inventoryAPI } from '../services/api';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = () => {
    setLoading(true);
    inventoryAPI.alerts(unreadOnly).then(r => { setAlerts(r.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(load, [unreadOnly]);

  const markRead = async (id) => {
    await inventoryAPI.markAlertRead(id);
    load();
  };

  const unreadCount = alerts.filter(a => !a.is_read).length;

  return (
    <div className="page">
      <div className="page-title">🔔 Alerts</div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <strong>{unreadCount}</strong> unread alert{unreadCount !== 1 ? 's' : ''}
          </div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={unreadOnly} onChange={e => setUnreadOnly(e.target.checked)} />
            Show unread only
          </label>
        </div>

        {loading ? <div className="loading">Loading alerts...</div>
          : alerts.length === 0 ? <div style={{ color: '#aaa', textAlign: 'center', padding: 30 }}>No alerts {unreadOnly ? '(unread)' : ''}. All good! ✅</div>
          : alerts.map(a => (
            <div key={a.id} className={`alert-item ${a.is_read ? 'alert-read' : 'alert-unread'}`}>
              <div style={{ fontSize: 20 }}>⚠️</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{a.message}</div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                  {new Date(a.created_at).toLocaleString()} · Type: {a.alert_type}
                </div>
              </div>
              {!a.is_read && (
                <button className="btn btn-sm" style={{ background: '#e8f5e9', color: '#2e7d32', whiteSpace: 'nowrap' }} onClick={() => markRead(a.id)}>
                  Mark Read
                </button>
              )}
              {a.is_read && <span style={{ fontSize: 11, color: '#aaa' }}>Read</span>}
            </div>
          ))
        }
      </div>
    </div>
  );
}
