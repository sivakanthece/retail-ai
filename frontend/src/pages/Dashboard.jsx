import React, { useEffect, useState, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, Area, AreaChart,
  Cell,
} from 'recharts';
import { analyticsAPI } from '../services/api';

/* ─── Palette ─────────────────────────────────────────────────────────── */
const CARD_GRADIENTS = [
  'linear-gradient(135deg,#6366f1,#8b5cf6)',
  'linear-gradient(135deg,#0ea5e9,#38bdf8)',
  'linear-gradient(135deg,#f59e0b,#fbbf24)',
  'linear-gradient(135deg,#ef4444,#f87171)',
  'linear-gradient(135deg,#8b5cf6,#a78bfa)',
];
const CAT_COLORS = [
  '#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444',
  '#8b5cf6','#06b6d4','#84cc16','#ec4899','#f97316',
];

function timeAgo(date) {
  const s = Math.floor((Date.now() - date) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

/* ─── Stat Card ────────────────────────────────────────────────────────── */
function StatCard({ label, value, icon, gradient, sub }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: gradient,
        borderRadius: 18,
        padding: '22px 24px',
        color: '#fff',
        boxShadow: hov
          ? '0 16px 48px rgba(0,0,0,0.22)'
          : '0 8px 28px rgba(0,0,0,0.13)',
        position: 'relative',
        overflow: 'hidden',
        cursor: 'default',
        transform: hov ? 'translateY(-4px)' : 'none',
        transition: 'transform 0.2s, box-shadow 0.2s',
      }}
    >
      <div style={{
        position: 'absolute', right: -20, top: -20,
        width: 100, height: 100, borderRadius: '50%',
        background: 'rgba(255,255,255,0.13)',
      }} />
      <div style={{
        position: 'absolute', right: 30, bottom: -30,
        width: 70, height: 70, borderRadius: '50%',
        background: 'rgba(255,255,255,0.08)',
      }} />
      <div style={{ fontSize: 30, marginBottom: 10 }}>{icon}</div>
      <div style={{ fontSize: 36, fontWeight: 800, lineHeight: 1, letterSpacing: '-1px' }}>
        {value ?? '—'}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, opacity: 0.85, marginTop: 6 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, opacity: 0.6, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function SectionTitle({ icon, title }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: '#1e293b' }}>{title}</span>
    </div>
  );
}

function GlassCard({ children, style = {} }) {
  return (
    <div style={{
      background: '#fff',
      borderRadius: 18,
      padding: '22px 24px',
      boxShadow: '0 4px 24px rgba(99,102,241,0.07)',
      border: '1px solid rgba(226,232,240,0.9)',
      ...style,
    }}>
      {children}
    </div>
  );
}

function DailyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'linear-gradient(135deg,#1e1b4b,#312e81)',
      borderRadius: 12, padding: '10px 16px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.3)', color: '#fff',
    }}>
      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 13 }}>{label}</div>
      <div style={{ fontSize: 12 }}>🛒 <b>{payload[0]?.value}</b> items</div>
      {payload[1] && <div style={{ fontSize: 12, marginTop: 2 }}>📷 <b>{payload[1]?.value}</b> scans</div>}
    </div>
  );
}

function CatTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'linear-gradient(135deg,#0f172a,#1e293b)',
      borderRadius: 12, padding: '10px 16px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.3)', color: '#fff', fontSize: 13,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{payload[0]?.payload?.category}</div>
      <div>📦 <b>{payload[0]?.value}</b> products</div>
      {payload[1] && <div style={{ marginTop: 2 }}>🔢 <b>{payload[1]?.value}</b> units</div>}
    </div>
  );
}

function EmptyState({ emoji, text }) {
  return (
    <div style={{ textAlign: 'center', padding: '50px 20px', color: '#94a3b8' }}>
      <div style={{ fontSize: 44, marginBottom: 10, opacity: 0.35 }}>{emoji}</div>
      <div style={{ fontSize: 13 }}>{text}</div>
    </div>
  );
}

/* ─── Main ─────────────────────────────────────────────────────────────── */
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    analyticsAPI.dashboard()
      .then(r => { setData(r.data); setLastFetch(new Date()); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && !data) return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '60vh', gap: 16, color: '#94a3b8',
    }}>
      <div style={{ fontSize: 52 }}>📊</div>
      <div style={{ fontSize: 15, fontWeight: 600, color: '#475569' }}>Loading dashboard…</div>
      <div style={{ width: 220, height: 5, background: '#e2e8f0', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          width: '45%', height: '100%',
          background: 'linear-gradient(90deg,#6366f1,#8b5cf6)',
          borderRadius: 99,
          animation: 'shimmer 1.2s ease-in-out infinite',
        }} />
      </div>
      <style>{`@keyframes shimmer{0%{margin-left:-45%}100%{margin-left:100%}}`}</style>
    </div>
  );

  if (!data) return (
    <div style={{ padding: 40, textAlign: 'center', color: '#ef4444', fontSize: 14 }}>
      Failed to load dashboard. Is the backend running?
    </div>
  );

  const hasDetections = data.daily_detections_chart.some(d => d.items > 0);
  const hasCategories = data.category_chart.length > 0;
  const stockPct = data.total_products
    ? Math.round(((data.total_products - data.out_of_stock_count) / data.total_products) * 100)
    : 100;

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#1e293b', letterSpacing: '-0.5px' }}>
            📊 Dashboard
          </div>
          <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 3 }}>
            Retail AI — real-time store intelligence
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {lastFetch && (
            <div style={{
              fontSize: 12, color: '#64748b',
              background: '#f1f5f9', padding: '6px 14px',
              borderRadius: 99, border: '1px solid #e2e8f0',
            }}>
              🕐 Updated {timeAgo(lastFetch)}
            </div>
          )}
          <button onClick={fetchData} disabled={loading} style={{
            padding: '8px 20px', borderRadius: 99,
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
            color: '#fff', border: 'none', cursor: loading ? 'default' : 'pointer',
            fontWeight: 600, fontSize: 13,
            boxShadow: '0 4px 14px rgba(99,102,241,0.4)',
            opacity: loading ? 0.7 : 1,
            display: 'flex', alignItems: 'center', gap: 6,
            transition: 'opacity 0.2s',
          }}>
            {loading ? '⏳' : '🔄'} Refresh
          </button>
        </div>
      </div>

      {/* ── Stat Cards ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: 16, marginBottom: 22,
      }}>
        <StatCard icon="📦" label="Total Products"  value={data.total_products}               gradient={CARD_GRADIENTS[0]} sub="across all categories" />
        <StatCard icon="🔢" label="Total Units"     value={data.total_quantity?.toLocaleString()} gradient={CARD_GRADIENTS[1]} sub="in inventory" />
        <StatCard icon="⚠️" label="Low Stock"       value={data.low_stock_count}              gradient={CARD_GRADIENTS[2]} sub="need restocking" />
        <StatCard icon="🚫" label="Out of Stock"    value={data.out_of_stock_count}           gradient={CARD_GRADIENTS[3]} sub="zero quantity" />
        <StatCard icon="🔔" label="Unread Alerts"   value={data.unread_alerts}                gradient={CARD_GRADIENTS[4]} sub="action required" />
      </div>

      {/* ── Stock health bar ── */}
      <GlassCard style={{ marginBottom: 22, padding: '14px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#475569', display: 'flex', alignItems: 'center', gap: 8 }}>
            📈 Stock Health
            <span style={{
              padding: '2px 10px', borderRadius: 99, fontSize: 12, fontWeight: 800,
              background: stockPct >= 80 ? '#dcfce7' : stockPct >= 50 ? '#fef3c7' : '#fee2e2',
              color: stockPct >= 80 ? '#16a34a' : stockPct >= 50 ? '#d97706' : '#dc2626',
            }}>
              {stockPct}%
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>
            {data.total_products - data.out_of_stock_count} / {data.total_products} products available
          </div>
        </div>
        <div style={{ background: '#e2e8f0', borderRadius: 99, height: 9, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 99,
            width: `${stockPct}%`,
            background: stockPct >= 80
              ? 'linear-gradient(90deg,#10b981,#34d399)'
              : stockPct >= 50
              ? 'linear-gradient(90deg,#f59e0b,#fbbf24)'
              : 'linear-gradient(90deg,#ef4444,#f87171)',
            transition: 'width 1s cubic-bezier(.4,0,.2,1)',
            boxShadow: stockPct >= 80
              ? '0 0 10px rgba(16,185,129,0.5)'
              : stockPct >= 50
              ? '0 0 10px rgba(245,158,11,0.5)'
              : '0 0 10px rgba(239,68,68,0.5)',
          }} />
        </div>
      </GlassCard>

      {/* ── Charts Row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 20, marginBottom: 20 }}>

        {/* Detection Activity */}
        <GlassCard>
          <SectionTitle icon="📅" title="Detection Activity — Last 14 Days" />
          {!hasDetections
            ? <EmptyState emoji="📷" text="No scans yet. Upload a shelf image on the Detection page." />
            : (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={data.daily_detections_chart}
                           margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradItems" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradScans" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#10b981" stopOpacity={0.22} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} interval={1} />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<DailyTooltip />} cursor={{ stroke: 'rgba(99,102,241,0.12)', strokeWidth: 20 }} />
                  <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={8} />
                  <Area
                    type="monotone" dataKey="items" name="Items detected"
                    stroke="#6366f1" strokeWidth={2.5} fill="url(#gradItems)"
                    dot={{ r: 3, fill: '#6366f1', strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: '#6366f1', stroke: '#fff', strokeWidth: 2 }}
                  />
                  <Area
                    type="monotone" dataKey="scans" name="Scans"
                    stroke="#10b981" strokeWidth={2} strokeDasharray="5 3" fill="url(#gradScans)"
                    dot={{ r: 3, fill: '#10b981', strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )
          }
        </GlassCard>

        {/* Category breakdown */}
        <GlassCard>
          <SectionTitle icon="🗂️" title="Inventory by Category" />
          {!hasCategories
            ? <EmptyState emoji="📦" text="No products yet — add via Detection page." />
            : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={data.category_chart}
                  layout="vertical"
                  margin={{ top: 0, right: 20, left: 60, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="category" tick={{ fontSize: 10, fill: '#475569' }} width={58} axisLine={false} tickLine={false} />
                  <Tooltip content={<CatTooltip />} cursor={{ fill: 'rgba(99,102,241,0.05)' }} />
                  <Bar dataKey="products" name="Products" radius={[0, 6, 6, 0]} maxBarSize={18}>
                    {data.category_chart.map((_, i) => (
                      <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </GlassCard>
      </div>

      {/* ── Bottom row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 20 }}>

        {/* Recent scans */}
        <GlassCard>
          <SectionTitle icon="🕐" title="Recent Scans" />
          {!data.recent_scans?.length
            ? <EmptyState emoji="📷" text="No scans yet." />
            : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.recent_scans.map((s, i) => (
                  <div key={s.id} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '12px 14px', borderRadius: 12,
                    background: i === 0 ? 'linear-gradient(135deg,#eef2ff,#e0e7ff)' : '#f8fafc',
                    border: '1px solid ' + (i === 0 ? '#c7d2fe' : '#e2e8f0'),
                  }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: 10, flexShrink: 0,
                      background: i === 0
                        ? 'linear-gradient(135deg,#6366f1,#8b5cf6)'
                        : 'linear-gradient(135deg,#cbd5e1,#94a3b8)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: '#fff', fontWeight: 800, fontSize: i === 0 ? 18 : 13,
                    }}>
                      {i === 0 ? '🆕' : `#${i + 1}`}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: 14, color: '#1e293b' }}>
                        {s.total_items} items detected
                      </div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                        {s.detected_at}
                      </div>
                    </div>
                    {i === 0 && (
                      <span style={{
                        padding: '3px 10px', borderRadius: 99, fontSize: 10, fontWeight: 700,
                        background: '#6366f1', color: '#fff', letterSpacing: '0.04em',
                      }}>
                        LATEST
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )
          }
        </GlassCard>

        {/* Low stock table */}
        <GlassCard>
          <SectionTitle icon="⚠️" title="Low Stock Products" />
          {!data.low_stock_products.length
            ? (
              <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                <div style={{ fontSize: 42, marginBottom: 8 }}>✅</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#10b981' }}>
                  All products are well-stocked!
                </div>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: '0 6px' }}>
                  <thead>
                    <tr>
                      {['SKU', 'Product', 'Qty', 'Threshold', 'Status'].map(h => (
                        <th key={h} style={{
                          padding: '6px 12px', fontSize: 10, fontWeight: 700,
                          color: '#94a3b8', textAlign: 'left',
                          textTransform: 'uppercase', letterSpacing: '0.06em',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.low_stock_products.map(p => {
                      const isOut = p.quantity === 0;
                      return (
                        <tr key={p.sku}>
                          <td style={{
                            padding: '11px 12px',
                            borderRadius: '10px 0 0 10px',
                            background: isOut ? '#fff5f5' : '#fffbeb',
                            fontSize: 12, color: '#64748b', fontFamily: 'monospace',
                          }}>
                            {p.sku}
                          </td>
                          <td style={{
                            padding: '11px 12px',
                            background: isOut ? '#fff5f5' : '#fffbeb',
                            fontSize: 13, fontWeight: 600, color: '#1e293b',
                          }}>
                            {p.name}
                          </td>
                          <td style={{ padding: '11px 12px', background: isOut ? '#fff5f5' : '#fffbeb' }}>
                            <span style={{
                              fontWeight: 800, fontSize: 15,
                              color: isOut ? '#ef4444' : '#f59e0b',
                            }}>
                              {p.quantity}
                            </span>
                          </td>
                          <td style={{
                            padding: '11px 12px',
                            background: isOut ? '#fff5f5' : '#fffbeb',
                            fontSize: 13, color: '#64748b',
                          }}>
                            {p.threshold}
                          </td>
                          <td style={{
                            padding: '11px 12px',
                            borderRadius: '0 10px 10px 0',
                            background: isOut ? '#fff5f5' : '#fffbeb',
                          }}>
                            <span style={{
                              padding: '4px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                              background: isOut ? '#fee2e2' : '#fef3c7',
                              color: isOut ? '#dc2626' : '#d97706',
                              display: 'inline-flex', alignItems: 'center', gap: 4,
                            }}>
                              {isOut ? '🚫 Out of Stock' : '⚠️ Low Stock'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          }
        </GlassCard>
      </div>
    </div>
  );
}
