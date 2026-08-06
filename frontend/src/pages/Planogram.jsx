import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';

const COMPLIANCE_COLORS = {
  ok:           { bg: '#dcfce7', color: '#15803d', label: '✅ OK' },
  mismatch:     { bg: '#fee2e2', color: '#dc2626', label: '⚠️ Mismatch' },
  out_of_stock: { bg: '#fee2e2', color: '#dc2626', label: '🔴 Out of Stock' },
  unidentified: { bg: '#fff7ed', color: '#c2410c', label: '❓ Unidentified' },
  no_planogram: { bg: '#f1f5f9', color: '#64748b', label: '— No Data' },
};

function Badge({ status }) {
  const s = COMPLIANCE_COLORS[status] || COMPLIANCE_COLORS.no_planogram;
  return (
    <span style={{
      background: s.bg, color: s.color,
      padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 700,
    }}>{s.label}</span>
  );
}

export default function Planogram() {
  const [shelves, setShelves]         = useState([]);
  const [selectedShelf, setSelected]  = useState('');
  const [entries, setEntries]         = useState([]);
  const [loading, setLoading]         = useState(false);
  const [importMsg, setImportMsg]     = useState(null);
  const [importErr, setImportErr]     = useState(null);
  const [viewMode, setViewMode]       = useState('grid'); // 'grid' | 'table'
  const [depthEdits, setDepthEdits]   = useState({}); // {entryId: value}
  const fileRef = useRef();

  // ── Load shelf list ───────────────────────────────────────────
  const loadShelves = async (resetSelection = false) => {
    try {
      const r = await api.get('/planogram/shelves');
      const d = r.data;
      setShelves(d.shelves || []);
      if (d.shelves?.length && (resetSelection || !selectedShelf)) {
        setSelected(d.shelves[0].shelf_id);
      }
    } catch (e) { console.error(e); }
  };

  // ── Load entries for selected shelf ──────────────────────────
  const loadEntries = async (shelfId) => {
    if (!shelfId) return;
    setLoading(true);
    try {
      const r = await api.get(`/planogram/?shelf_id=${shelfId}`);
      setEntries(r.data.entries || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadShelves(); }, []);
  useEffect(() => { loadEntries(selectedShelf); }, [selectedShelf]);

  // ── CSV import ────────────────────────────────────────────────
  const handleImport = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files[0];
    if (!file) return;
    setImportMsg(null); setImportErr(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await api.post('/planogram/import-csv?replace_shelf=ALL', form);
      setImportMsg(`Imported ${r.data.inserted} entries successfully.`);
      await loadShelves(true);  // reset selection to first shelf in new data
    } catch (err) {
      setImportErr(err.response?.data?.detail || String(err));
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  // ── Delete entry ──────────────────────────────────────────────
  const handleDelete = async (id) => {
    if (!window.confirm('Delete this planogram entry?')) return;
    await api.delete(`/planogram/${id}`);
    loadEntries(selectedShelf);
  };

  // ── Save depth edit ───────────────────────────────────────────
  const saveDepth = async (entry) => {
    const val = parseInt(depthEdits[entry.id]);
    if (isNaN(val) || val < 1) return;
    try {
      await api.put(`/planogram/${entry.id}`, {
        store_id:        entry.store_id,
        shelf_id:        entry.shelf_id,
        shelf_name:      entry.shelf_name || '',
        row:             entry.row,
        col:             entry.col,
        product_name:    entry.product_name,
        brand:           entry.brand || '',
        sku:             entry.sku   || '',
        category:        entry.category || '',
        facings:         entry.facings || 1,
        depth:           val,
        unit_price_usd:  entry.unit_price_usd || 0,
        planogram_notes: entry.planogram_notes || '',
      });
      setDepthEdits(prev => { const n = {...prev}; delete n[entry.id]; return n; });
      loadEntries(selectedShelf);
    } catch (e) {
      alert('Save failed: ' + (e.response?.data?.detail || e.message));
    }
  };

  // ── Grid view helpers ─────────────────────────────────────────
  const maxRow = entries.length ? Math.max(...entries.map(e => e.row)) : 0;
  const maxCol = entries.length ? Math.max(...entries.map(e => e.col)) : 0;
  const gridMap = {};
  entries.forEach(e => { gridMap[`${e.row}-${e.col}`] = e; });

  const shelfName = shelves.find(s => s.shelf_id === selectedShelf)?.shelf_name || selectedShelf;

  return (
    <div style={{ padding: '24px', maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, color: '#0f172a', margin: 0 }}>
          📋 Planogram Manager
        </h1>
        <p style={{ color: '#64748b', marginTop: 4, fontSize: 14 }}>
          Define expected shelf layouts and check compliance against detected products.
        </p>
      </div>

      {/* Import CSV */}
      <div style={{
        background: '#f8fafc', border: '1px solid #e2e8f0',
        borderRadius: 10, padding: '16px 20px', marginBottom: 24,
      }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 15, color: '#1e293b' }}>
          Import Planogram CSV
        </h3>
        <form onSubmit={handleImport} style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="file" accept=".csv" ref={fileRef}
            style={{ fontSize: 13, color: '#334155' }}
          />
          <button type="submit" style={{
            background: '#1e40af', color: '#fff',
            border: 'none', borderRadius: 6,
            padding: '7px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
          }}>Upload & Import</button>
          <span style={{ fontSize: 12, color: '#94a3b8' }}>
            Clears existing data and imports fresh. Use <code>planogram_sample.csv</code> from demo_images/.
          </span>
        </form>
        {importMsg && <div style={{ marginTop: 8, color: '#15803d', fontSize: 13 }}>✅ {importMsg}</div>}
        {importErr && <div style={{ marginTop: 8, color: '#dc2626', fontSize: 13 }}>❌ {importErr}</div>}
      </div>

      {/* Shelf selector + view toggle */}
      {shelves.length > 0 && (
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
          <div>
            <label style={{ fontSize: 13, color: '#64748b', marginRight: 8 }}>Shelf:</label>
            <select
              value={selectedShelf}
              onChange={e => setSelected(e.target.value)}
              style={{
                padding: '6px 12px', borderRadius: 6,
                border: '1px solid #cbd5e1', fontSize: 13,
              }}
            >
              {shelves.map(s => (
                <option key={s.shelf_id} value={s.shelf_id}>
                  {s.shelf_id} — {s.shelf_name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            {['grid', 'table'].map(m => (
              <button key={m} onClick={() => setViewMode(m)} style={{
                padding: '5px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: 'pointer',
                background: viewMode === m ? '#1e40af' : '#e2e8f0',
                color: viewMode === m ? '#fff' : '#475569',
                border: 'none',
              }}>{m === 'grid' ? '⊞ Grid' : '☰ Table'}</button>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      {shelves.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 20px',
          background: '#f8fafc', borderRadius: 10,
          border: '2px dashed #cbd5e1',
        }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#334155', marginBottom: 8 }}>
            No planogram data yet
          </div>
          <div style={{ fontSize: 13, color: '#64748b' }}>
            Import <strong>planogram_sample.csv</strong> from the demo_images/ folder to get started.
          </div>
        </div>
      ) : loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>Loading…</div>
      ) : viewMode === 'grid' ? (
        /* ── Grid View ── */
        <div>
          <h3 style={{ fontSize: 14, color: '#64748b', marginBottom: 12 }}>
            {shelfName} — {maxRow} row{maxRow !== 1 ? 's' : ''} × {maxCol} column{maxCol !== 1 ? 's' : ''}
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 6 }}>
              <thead>
                <tr>
                  <th style={{ fontSize: 11, color: '#94a3b8', padding: '4px 6px' }}>Row ↓ / Col →</th>
                  {Array.from({ length: maxCol }, (_, c) => (
                    <th key={c} style={{ fontSize: 11, color: '#94a3b8', padding: '4px 8px', minWidth: 120 }}>
                      Col {c + 1}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: maxRow }, (_, r) => (
                  <tr key={r}>
                    <td style={{ fontSize: 11, color: '#94a3b8', paddingRight: 8, whiteSpace: 'nowrap' }}>
                      Row {r + 1}
                    </td>
                    {Array.from({ length: maxCol }, (_, c) => {
                      const entry = gridMap[`${r + 1}-${c + 1}`];
                      return (
                        <td key={c}>
                          {entry ? (
                            <div style={{
                              background: '#fff', border: '1px solid #e2e8f0',
                              borderRadius: 8, padding: '8px 10px',
                              minHeight: 80, position: 'relative',
                            }}>
                              <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginBottom: 2 }}>
                                {entry.product_name}
                              </div>
                              <div style={{ fontSize: 11, color: '#64748b' }}>{entry.brand}</div>
                              <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
                                {entry.sku} · ${entry.unit_price_usd?.toFixed(2)}
                              </div>
                              <div style={{ marginTop: 4, display:'flex', gap:4, flexWrap:'wrap', alignItems:'center' }}>
                                <span style={{
                                  fontSize: 9, background: '#eff6ff', color: '#1d4ed8',
                                  padding: '1px 5px', borderRadius: 3, fontWeight: 600,
                                }}>{entry.category}</span>
                                <span style={{
                                  fontSize: 9, background: '#fef3c7', color: '#92400e',
                                  padding: '1px 5px', borderRadius: 3, fontWeight: 600,
                                }} title="Shelf depth (units stacked back-to-front)">
                                  ↕ {entry.depth ?? 1}
                                </span>
                              </div>
                              <button
                                onClick={() => handleDelete(entry.id)}
                                style={{
                                  position: 'absolute', top: 4, right: 4,
                                  background: 'none', border: 'none',
                                  color: '#cbd5e1', cursor: 'pointer', fontSize: 14,
                                }}
                                title="Delete"
                              >×</button>
                            </div>
                          ) : (
                            <div style={{
                              background: '#f8fafc', border: '1px dashed #cbd5e1',
                              borderRadius: 8, minHeight: 80,
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}>
                              <span style={{ color: '#cbd5e1', fontSize: 11 }}>empty</span>
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* ── Table View ── */
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f1f5f9' }}>
                {['Row', 'Col', 'Product', 'Brand', 'SKU', 'Category', 'Facings', 'Depth', 'Price', ''].map(h => (
                  <th key={h} style={{
                    padding: '8px 12px', textAlign: 'left',
                    color: '#64748b', fontSize: 11, fontWeight: 700,
                    borderBottom: '1px solid #e2e8f0',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(e => {
                const editingDepth = depthEdits[e.id] !== undefined;
                return (
                  <tr key={e.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '7px 12px', color: '#475569' }}>{e.row}</td>
                    <td style={{ padding: '7px 12px', color: '#475569' }}>{e.col}</td>
                    <td style={{ padding: '7px 12px', fontWeight: 600, color: '#0f172a' }}>{e.product_name}</td>
                    <td style={{ padding: '7px 12px', color: '#475569' }}>{e.brand}</td>
                    <td style={{ padding: '7px 12px', color: '#64748b', fontFamily: 'monospace', fontSize: 11 }}>{e.sku}</td>
                    <td style={{ padding: '7px 12px' }}>
                      <span style={{
                        background: '#eff6ff', color: '#1d4ed8',
                        padding: '2px 6px', borderRadius: 3, fontSize: 11, fontWeight: 600,
                      }}>{e.category}</span>
                    </td>
                    <td style={{ padding: '7px 12px', color: '#475569' }}>{e.facings}</td>
                    {/* Depth — inline editable */}
                    <td style={{ padding: '7px 12px' }}>
                      {editingDepth ? (
                        <div style={{ display:'flex', gap:4, alignItems:'center' }}>
                          <input
                            type="number" min="1"
                            value={depthEdits[e.id]}
                            onChange={ev => setDepthEdits(prev => ({ ...prev, [e.id]: ev.target.value }))}
                            style={{ width:50, fontSize:12, padding:'2px 5px', borderRadius:4, border:'1px solid #c4b5fd' }}
                          />
                          <button onClick={() => saveDepth(e)}
                            style={{ background:'#6d28d9', color:'#fff', border:'none', borderRadius:3, padding:'2px 6px', cursor:'pointer', fontSize:11 }}>✓</button>
                          <button onClick={() => setDepthEdits(prev => { const n={...prev}; delete n[e.id]; return n; })}
                            style={{ background:'#eee', border:'none', borderRadius:3, padding:'2px 5px', cursor:'pointer', fontSize:11 }}>✕</button>
                        </div>
                      ) : (
                        <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                          <span style={{ fontWeight:600, color:'#475569' }}>{e.depth ?? 1}</span>
                          <button
                            onClick={() => setDepthEdits(prev => ({ ...prev, [e.id]: e.depth ?? 1 }))}
                            title="Edit depth"
                            style={{ fontSize:10, background:'none', border:'none', cursor:'pointer', color:'#94a3b8' }}>
                            ✏️
                          </button>
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '7px 12px', color: '#475569' }}>${e.unit_price_usd?.toFixed(2)}</td>
                    <td style={{ padding: '7px 12px' }}>
                      <button onClick={() => handleDelete(e.id)} style={{
                        background: '#fee2e2', color: '#dc2626',
                        border: 'none', borderRadius: 4,
                        padding: '2px 8px', cursor: 'pointer', fontSize: 11,
                      }}>Delete</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div style={{ marginTop: 8, color: '#94a3b8', fontSize: 12 }}>
            {entries.length} entries
          </div>
        </div>
      )}
    </div>
  );
}
