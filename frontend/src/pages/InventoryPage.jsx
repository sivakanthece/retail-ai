import React, { useEffect, useState } from 'react';
import { inventoryAPI } from '../services/api';
import api from '../services/api';

export default function InventoryPage({ user }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editId, setEditId] = useState(null);
  const [editQty, setEditQty] = useState('');
  const [editLoc, setEditLoc] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newProd, setNewProd] = useState({ sku:'', name:'', category:'', low_stock_threshold:10, initial_quantity:0, shelf_location:'' });
  // Inline patch state — {productId: {threshold, name, category, _editing}}
  const [patches, setPatches] = useState({});
  const canEdit = ['admin','manager'].includes(user?.role);

  const load = () => {
    setLoading(true);
    inventoryAPI.list().then(r => { setItems(r.data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const saveEdit = async (id) => {
    await inventoryAPI.update(id, { quantity: parseInt(editQty), shelf_location: editLoc });
    setEditId(null);
    load();
  };

  const addProduct = async () => {
    await inventoryAPI.createProduct(newProd);
    setShowAdd(false);
    setNewProd({ sku:'', name:'', category:'', low_stock_threshold:10, initial_quantity:0, shelf_location:'' });
    load();
  };

  // Save name / category / threshold patch
  const savePatch = async (id) => {
    const p = patches[id] || {};
    const body = {};
    if (p.name      !== undefined) body.name = p.name;
    if (p.category  !== undefined) body.category = p.category;
    if (p.threshold !== undefined) body.low_stock_threshold = parseInt(p.threshold);
    try {
      await api.patch(`/inventory/products/${id}`, body);
      setPatches(prev => { const n = {...prev}; delete n[id]; return n; });
      load();
    } catch (e) {
      alert('Failed to save: ' + (e.response?.data?.detail || e.message));
    }
  };

  const startPatch = (item) => setPatches(prev => ({
    ...prev,
    [item.id]: { name: item.name, category: item.category, threshold: item.low_stock_threshold, _editing: true },
  }));
  const cancelPatch = (id) => setPatches(prev => { const n = {...prev}; delete n[id]; return n; });

  const filtered = items.filter(i =>
    i.name.toLowerCase().includes(search.toLowerCase()) ||
    i.sku.toLowerCase().includes(search.toLowerCase()) ||
    i.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page">
      <div className="page-title">📦 Inventory Management</div>

      <div className="card">
        <div style={{ display: 'flex', gap: 12, marginBottom: 14, alignItems: 'center' }}>
          <input placeholder="Search by name, SKU, category..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 320 }} />
          {canEdit && <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>+ Add Product</button>}
        </div>

        {showAdd && canEdit && (
          <div style={{ background: '#f5f6fa', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>New Product</div>
            <div className="form-row">
              <div className="form-group"><label>SKU</label><input value={newProd.sku} onChange={e => setNewProd({...newProd, sku: e.target.value})} placeholder="SKU-001" /></div>
              <div className="form-group"><label>Name</label><input value={newProd.name} onChange={e => setNewProd({...newProd, name: e.target.value})} placeholder="Product name" /></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Category</label><input value={newProd.category} onChange={e => setNewProd({...newProd, category: e.target.value})} placeholder="Beverages" /></div>
              <div className="form-group"><label>Shelf Location</label><input value={newProd.shelf_location} onChange={e => setNewProd({...newProd, shelf_location: e.target.value})} placeholder="A1" /></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Initial Quantity</label><input type="number" value={newProd.initial_quantity} onChange={e => setNewProd({...newProd, initial_quantity: parseInt(e.target.value)})} /></div>
              <div className="form-group"><label>Low Stock Threshold</label><input type="number" value={newProd.low_stock_threshold} onChange={e => setNewProd({...newProd, low_stock_threshold: parseInt(e.target.value)})} /></div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={addProduct}>Save Product</button>
            <button className="btn btn-sm" style={{ marginLeft: 8, background: '#eee' }} onClick={() => setShowAdd(false)}>Cancel</button>
          </div>
        )}

        {loading ? <div className="loading">Loading inventory...</div> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Product</th>
                  <th>Category</th>
                  <th>Quantity</th>
                  <th>Location</th>
                  <th>Threshold</th>
                  <th>Status</th>
                  {canEdit && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filtered.map(item => {
                  const patch = patches[item.id];
                  const isEditingPatch = patch?._editing;
                  const isEditingQty   = editId === item.id;

                  return (
                    <tr key={item.id}>
                      <td style={{ fontSize:12, color:'#64748b', fontFamily:'monospace' }}>{item.sku}</td>

                      {/* Product name — inline editable */}
                      <td>
                        {isEditingPatch ? (
                          <input
                            value={patch.name}
                            onChange={e => setPatches(prev => ({ ...prev, [item.id]: { ...prev[item.id], name: e.target.value } }))}
                            style={{ width: 150, fontSize: 12, padding: '3px 6px', borderRadius: 4, border: '1px solid #c4b5fd' }}
                          />
                        ) : (
                          <span style={{ fontWeight: 600 }}>{item.name}</span>
                        )}
                      </td>

                      {/* Category — inline editable */}
                      <td>
                        {isEditingPatch ? (
                          <input
                            value={patch.category}
                            onChange={e => setPatches(prev => ({ ...prev, [item.id]: { ...prev[item.id], category: e.target.value } }))}
                            style={{ width: 130, fontSize: 12, padding: '3px 6px', borderRadius: 4, border: '1px solid #c4b5fd' }}
                          />
                        ) : (
                          <span style={{ background:'#ede9fe', color:'#6d28d9', borderRadius:99,
                            padding:'2px 8px', fontSize:11, fontWeight:600 }}>{item.category}</span>
                        )}
                      </td>

                      {/* Quantity */}
                      <td>
                        {isEditingQty
                          ? <input type="number" value={editQty} onChange={e => setEditQty(e.target.value)} style={{ width: 70 }} />
                          : <strong style={{ color: item.is_low_stock ? '#c53030' : '#333' }}>{item.quantity}</strong>
                        }
                      </td>

                      {/* Location */}
                      <td>
                        {isEditingQty
                          ? <input value={editLoc} onChange={e => setEditLoc(e.target.value)} style={{ width: 80 }} />
                          : item.shelf_location
                        }
                      </td>

                      {/* Threshold — inline editable */}
                      <td>
                        {isEditingPatch ? (
                          <input
                            type="number"
                            value={patch.threshold}
                            onChange={e => setPatches(prev => ({ ...prev, [item.id]: { ...prev[item.id], threshold: e.target.value } }))}
                            style={{ width: 60, fontSize: 12, padding: '3px 6px', borderRadius: 4, border: '1px solid #c4b5fd' }}
                          />
                        ) : (
                          <span style={{ fontWeight: 600, color: '#475569' }}>{item.low_stock_threshold}</span>
                        )}
                      </td>

                      {/* Status */}
                      <td>
                        <span className={`badge ${item.quantity === 0 ? 'badge-red' : item.is_low_stock ? 'badge-orange' : 'badge-green'}`}>
                          {item.quantity === 0 ? 'Out' : item.is_low_stock ? 'Low' : 'OK'}
                        </span>
                      </td>

                      {/* Actions */}
                      {canEdit && (
                        <td>
                          <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
                            {/* Qty/location edit */}
                            {isEditingQty ? (
                              <>
                                <button className="btn btn-primary btn-sm" onClick={() => saveEdit(item.id)}>Save</button>
                                <button className="btn btn-sm" style={{ background:'#eee' }} onClick={() => setEditId(null)}>✕</button>
                              </>
                            ) : (
                              <button className="btn btn-sm" style={{ background:'#e8eaf6', color:'#1a237e' }}
                                onClick={() => { setEditId(item.id); setEditQty(item.quantity); setEditLoc(item.shelf_location); }}>
                                Qty
                              </button>
                            )}
                            {/* Name/category/threshold patch */}
                            {isEditingPatch ? (
                              <>
                                <button className="btn btn-primary btn-sm" onClick={() => savePatch(item.id)}>Save</button>
                                <button className="btn btn-sm" style={{ background:'#eee' }} onClick={() => cancelPatch(item.id)}>✕</button>
                              </>
                            ) : (
                              <button className="btn btn-sm" style={{ background:'#fef3c7', color:'#92400e' }}
                                onClick={() => startPatch(item)}>
                                Edit
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
