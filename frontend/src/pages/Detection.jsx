import React, { useState, useRef, useEffect, useCallback } from 'react';
import { detectionAPI } from '../services/api';

// ── Stage pipeline progress banner ──────────────────────────────
const STAGE_INFO = [
  { id: 1, icon: '🔲', label: 'Object Detection',        desc: 'YOLOv8 locating products' },
  { id: 2, icon: '🏷️', label: 'Category Classification', desc: 'CLIP assigning categories' },
  { id: 3, icon: '🔎', label: 'SKU Matching',            desc: 'Searching product library' },
];

function PipelineBanner({ currentStage, stats }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg,#0f172a,#1e1b4b)',
      borderRadius: 16, padding: '18px 22px', marginBottom: 16, color: '#fff',
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#a78bfa', marginBottom: 14, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        🧠 AI Pipeline Running
      </div>
      <div style={{ display: 'flex', gap: 0, alignItems: 'center', flexWrap: 'wrap' }}>
        {STAGE_INFO.map((s, i) => {
          const done    = s.id < currentStage;
          const active  = s.id === currentStage;
          const pending = s.id > currentStage;
          return (
            <React.Fragment key={s.id}>
              <div style={{
                flex: '1 1 140px', padding: '12px 14px', borderRadius: 10,
                background: done    ? 'rgba(16,185,129,0.2)'
                          : active  ? 'rgba(99,102,241,0.3)'
                          : 'rgba(255,255,255,0.06)',
                border: `1.5px solid ${done ? '#10b981' : active ? '#6366f1' : 'rgba(255,255,255,0.1)'}`,
                transition: 'all 0.4s',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 18 }}>
                    {done ? '✅' : active ? '⏳' : s.icon}
                  </span>
                  <span style={{
                    fontSize: 11, fontWeight: 700,
                    color: done ? '#34d399' : active ? '#a78bfa' : '#64748b',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>
                    Stage {s.id}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: done ? '#fff' : active ? '#e2e8f0' : '#475569' }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 11, color: done ? '#6ee7b7' : active ? '#818cf8' : '#334155', marginTop: 2 }}>
                  {done && s.id === 1 ? `${stats?.stage1_total ?? ''} products found`
                   : done && s.id === 2 ? `${stats?.stage2_classified ?? ''} classified`
                   : done && s.id === 3 ? `${stats?.stage3_matched ?? 0} matched, ${stats?.stage3_unmatched ?? 0} unmatched`
                   : active ? s.desc + '…'
                   : 'Waiting…'}
                </div>
              </div>
              {i < STAGE_INFO.length - 1 && (
                <div style={{ padding: '0 6px', color: done ? '#10b981' : '#334155', fontSize: 18 }}>›</div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ── Bulk-save progress bar ────────────────────────────────────────
function BulkSaveProgress({ done, total, type, currentName }) {
  const pct  = total > 0 ? Math.round((done / total) * 100) : 0;
  const icon = type === 'library' ? '📚' : '💾';
  const label = type === 'library' ? 'Saving to Library' : 'Saving to Inventory';
  return (
    <div style={{
      background: 'linear-gradient(135deg,#1e1b4b,#0f172a)',
      borderRadius: 14, padding: '16px 20px', marginBottom: 14,
      color: '#fff', animation: 'fadeSlideIn 0.3s ease',
    }}>
      <style>{`@keyframes fadeSlideIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}`}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#a78bfa' }}>
          {icon} {label} — {done} of {total}
        </div>
        <div style={{ fontSize: 13, fontWeight: 800, color: '#34d399' }}>{pct}%</div>
      </div>
      {/* Track */}
      <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: 99, height: 8, overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 99,
          background: 'linear-gradient(90deg,#6366f1,#8b5cf6,#a78bfa)',
          width: `${pct}%`,
          transition: 'width 0.4s ease',
          boxShadow: '0 0 10px rgba(139,92,246,0.6)',
        }} />
      </div>
      {currentName && (
        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8, truncate: 'ellipsis' }}>
          ⏳ {currentName}
        </div>
      )}
    </div>
  );
}

// ── Add-to-library inline modal ───────────────────────────────────
function AddToLibraryModal({ bbox, eventId, onDone, onClose }) {
  const [name, setName]     = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');
  const submit = async () => {
    if (!name.trim()) { setError('Enter a product name.'); return; }
    setSaving(true); setError('');
    try {
      await detectionAPI.addToLibrary(eventId, bbox, name.trim());
      onDone(name.trim());
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed. Is CLIP available?');
    } finally { setSaving(false); }
  };
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.5)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:2000 }}>
      <div style={{ background:'#fff', borderRadius:14, padding:24, width:340, boxShadow:'0 8px 40px rgba(0,0,0,0.2)' }}>
        <div style={{ fontWeight:700, fontSize:16, marginBottom:14 }}>📚 Add to Product Library</div>
        <div style={{ fontSize:12, color:'#64748b', marginBottom:14 }}>
          This crop will be saved as a reference image for Stage 3 SKU matching.
        </div>
        <label style={{ display:'block', fontSize:12, fontWeight:600, color:'#475569', marginBottom:6 }}>Product Name *</label>
        <input
          autoFocus value={name} onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          placeholder="e.g. Pepsi Max 330ml Can"
          style={{ width:'100%', padding:'9px 12px', borderRadius:8, border:'1px solid #e2e8f0', fontSize:13, boxSizing:'border-box', marginBottom:8 }}
        />
        {error && <div style={{ color:'#dc2626', fontSize:12, marginBottom:8 }}>{error}</div>}
        <div style={{ display:'flex', gap:10, marginTop:6 }}>
          <button onClick={onClose} style={{ flex:1, padding:'9px', borderRadius:8, border:'1px solid #e2e8f0', cursor:'pointer', background:'#fff', fontSize:13 }}>
            Cancel
          </button>
          <button onClick={submit} disabled={saving || !name.trim()} style={{
            flex:1, padding:'9px', borderRadius:8, border:'none', cursor:'pointer',
            background:'linear-gradient(135deg,#6366f1,#8b5cf6)', color:'#fff', fontWeight:700, fontSize:13,
            opacity: (saving || !name.trim()) ? 0.6 : 1,
          }}>
            {saving ? '⏳ Saving…' : '💾 Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Live camera modal (desktop webcam / mobile fallback) ─────────
function CameraModal({ onCapture, onClose }) {
  const videoRef   = useRef();
  const streamRef  = useRef();
  const [ready,    setReady]    = useState(false);
  const [error,    setError]    = useState('');
  const [facing,   setFacing]   = useState('environment'); // rear cam by default

  const startStream = useCallback(async (facingMode) => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setReady(true);
        setError('');
      }
    } catch (e) {
      setError('Camera access denied or not available. Use "Upload Image" instead.');
    }
  }, []);

  useEffect(() => {
    startStream(facing);
    return () => streamRef.current?.getTracks().forEach(t => t.stop());
  }, [facing, startStream]);

  const snap = () => {
    const video  = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.toBlob(blob => {
      const file = new File([blob], `shelf-${Date.now()}.jpg`, { type: 'image/jpeg' });
      streamRef.current?.getTracks().forEach(t => t.stop());
      onCapture(file);
    }, 'image/jpeg', 0.92);
  };

  const toggleCamera = () => {
    const next = facing === 'environment' ? 'user' : 'environment';
    setFacing(next);
  };

  return (
    <div style={overlay}>
      <div style={{ ...modal, maxWidth: 680, padding: 0, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                      padding:'12px 16px', background:'#1a237e', color:'#fff' }}>
          <span style={{ fontWeight:700, fontSize:15 }}>📷 Camera</span>
          <div style={{ display:'flex', gap:10 }}>
            <button onClick={toggleCamera}
              style={{ background:'rgba(255,255,255,0.2)', border:'none', color:'#fff',
                       borderRadius:6, padding:'5px 12px', cursor:'pointer', fontSize:13 }}>
              🔄 Flip
            </button>
            <button onClick={onClose}
              style={{ background:'none', border:'none', color:'#fff', fontSize:22, cursor:'pointer', lineHeight:1 }}>
              ×
            </button>
          </div>
        </div>

        {/* Viewfinder */}
        <div style={{ background:'#000', position:'relative', minHeight:300 }}>
          <video ref={videoRef} playsInline muted
            style={{ width:'100%', display:'block', maxHeight:'60vh', objectFit:'cover' }} />
          {!ready && !error && (
            <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center',
                          justifyContent:'center', color:'#fff', fontSize:14 }}>
              Starting camera…
            </div>
          )}
          {error && (
            <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center',
                          justifyContent:'center', padding:20, color:'#fca5a5', fontSize:13, textAlign:'center' }}>
              {error}
            </div>
          )}
        </div>

        {/* Snap button */}
        <div style={{ padding:16, display:'flex', justifyContent:'center', background:'#111' }}>
          <button onClick={snap} disabled={!ready}
            style={{ width:64, height:64, borderRadius:'50%', border:'4px solid #fff',
                     background: ready ? '#fff' : '#555', cursor: ready ? 'pointer' : 'default',
                     display:'flex', alignItems:'center', justifyContent:'center', fontSize:28 }}>
            📸
          </button>
        </div>
      </div>
    </div>
  );
}

const CATEGORIES = [
  'Beverages','Snacks','Dairy','Bakery','Produce','Frozen',
  'Canned Goods','Condiments','Cereals','Personal Care','Household','General',
];

// ── Annotated shelf image with numbered boxes ────────────────────
function AnnotatedImage({ imageSrc, detections, groups }) {
  const canvasRef = useRef();
  const imgRef    = useRef();

  // Build index→color map from groups so same product = same colour
  const indexColorMap = {};
  if (groups) {
    const palette = ['#2563eb','#16a34a','#dc2626','#d97706','#7c3aed',
                     '#0891b2','#be185d','#15803d','#b45309','#1d4ed8'];
    groups.forEach((g, gi) => {
      const color = palette[gi % palette.length];
      g.indices.forEach(i => { indexColorMap[i] = color; });
    });
  }

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const img    = imgRef.current;
    if (!canvas || !img) return;
    const displayW = Math.min(700, canvas.parentElement?.clientWidth || 700);
    const scale    = displayW / img.naturalWidth;
    canvas.width   = displayW;
    canvas.height  = img.naturalHeight * scale;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    detections.forEach((d, i) => {
      const [x1, y1, x2, y2] = d.bbox;
      const sx = x1 * scale, sy = y1 * scale;
      const sw = (x2 - x1) * scale, sh = (y2 - y1) * scale;
      const color = indexColorMap[i] || '#2563eb';

      ctx.strokeStyle = color;
      ctx.lineWidth   = 2;
      ctx.strokeRect(sx, sy, sw, sh);

      const label = `#${i + 1}`;
      ctx.font = 'bold 10px sans-serif';
      const tw  = ctx.measureText(label).width + 6;
      ctx.fillStyle = color;
      ctx.fillRect(sx, sy - 15, tw, 15);
      ctx.fillStyle = '#fff';
      ctx.fillText(label, sx + 3, sy - 3);
    });
  }, [detections, groups]);

  useEffect(() => {
    const img = new window.Image();
    img.src = imageSrc;
    img.onload = () => { imgRef.current = img; draw(); };
  }, [imageSrc, draw]);

  useEffect(() => { if (imgRef.current) draw(); }, [groups, draw]);

  return (
    <div>
      <canvas ref={canvasRef} style={{ borderRadius: 8, display: 'block', maxWidth: '100%' }} />
      {groups && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>
          Same-coloured boxes = same product type
        </div>
      )}
    </div>
  );
}

// ── Small crop thumbnail ─────────────────────────────────────────
function CropThumb({ imageSrc, bbox, size = 56 }) {
  const canvasRef = useRef();
  useEffect(() => {
    const img = new window.Image();
    img.src = imageSrc;
    img.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const [x1, y1, x2, y2] = bbox;
      canvas.width = size; canvas.height = size;
      canvas.getContext('2d').drawImage(img, x1, y1, x2-x1, y2-y1, 0, 0, size, size);
    };
  }, [imageSrc, bbox, size]);
  return <canvas ref={canvasRef} width={size} height={size}
    style={{ borderRadius: 4, border: '1px solid #ddd', display: 'block' }} />;
}

// ── Add to DB modal ──────────────────────────────────────────────
function AddToDBModal({ group, imageSrc, onSave, onClose }) {
  const [form, setForm] = useState({
    name:                group.name || '',
    sku:                 group.sku  || `SKU-${Date.now()}`,
    category:            group.category || 'General',
    price:               group.estimated_price || '',
    quantity:            group.count || 1,
    low_stock_threshold: Math.max(5, Math.round((group.count || 1) * 0.3)),
    shelf_location:      '',
  });
  const [saving, setSaving] = useState(false);
  const [saved,  setSaved]  = useState(false);
  const [error,  setError]  = useState('');

  const handle = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) { setError('Product name is required.'); return; }
    setSaving(true); setError('');
    try {
      const res = await detectionAPI.saveProduct({
        ...form,
        price:               parseFloat(form.price) || 0,
        quantity:            parseInt(form.quantity) || 1,
        low_stock_threshold: parseInt(form.low_stock_threshold) || 10,
      });
      setSaved(true);
      onSave(group.name, res.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  if (saved) return (
    <div style={overlay}>
      <div style={modal}>
        <div style={{ textAlign: 'center', padding: 24 }}>
          <div style={{ fontSize: 52 }}>✅</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 10 }}>Added to Inventory!</div>
          <div style={{ color: '#555', marginTop: 6 }}><b>{form.name}</b> × {form.quantity} units</div>
          <button className="btn" style={{ marginTop: 20 }} onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );

  return (
    <div style={overlay}>
      <div style={modal}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
          <div style={{ fontWeight:700, fontSize:16 }}>📦 Add to Inventory</div>
          <button onClick={onClose} style={{ background:'none', border:'none', fontSize:22, cursor:'pointer' }}>×</button>
        </div>

        {/* Product preview */}
        <div style={{ display:'flex', gap:14, background:'#f0f7ff', borderRadius:8, padding:12, marginBottom:16 }}>
          {imageSrc && <CropThumb imageSrc={imageSrc} bbox={group.first_bbox} size={72} />}
          <div>
            <div style={{ fontWeight:700, fontSize:15 }}>{group.name}</div>
            <div style={{ color:'#555', fontSize:13, marginTop:2 }}>{group.brand}</div>
            <div style={{ marginTop:6, display:'flex', gap:8, flexWrap:'wrap' }}>
              <span style={{ background:'#dbeafe', color:'#1d4ed8', borderRadius:12, padding:'2px 10px', fontSize:12, fontWeight:600 }}>
                {group.count} units detected
              </span>
              <span style={{ background:'#dcfce7', color:'#15803d', borderRadius:12, padding:'2px 10px', fontSize:12, fontWeight:600 }}>
                {(group.avg_confidence * 100).toFixed(0)}% avg confidence
              </span>
            </div>
          </div>
        </div>

        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
          <div style={{ gridColumn:'1 / -1' }}>
            <label style={lbl}>Product Name *</label>
            <input style={inp} value={form.name} onChange={e => handle('name', e.target.value)} />
          </div>
          <div>
            <label style={lbl}>SKU</label>
            <input style={inp} value={form.sku} onChange={e => handle('sku', e.target.value)} />
          </div>
          <div>
            <label style={lbl}>Category</label>
            <select style={inp} value={form.category} onChange={e => handle('category', e.target.value)}>
              {CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Price ($)</label>
            <input style={inp} type="number" min="0" step="0.01"
              value={form.price} onChange={e => handle('price', e.target.value)} />
          </div>
          <div>
            <label style={lbl}>Quantity (detected: {group.count})</label>
            <input style={inp} type="number" min="1"
              value={form.quantity} onChange={e => handle('quantity', e.target.value)} />
          </div>
          <div>
            <label style={lbl}>Low Stock Alert At</label>
            <input style={inp} type="number" min="1"
              value={form.low_stock_threshold} onChange={e => handle('low_stock_threshold', e.target.value)} />
          </div>
          <div style={{ gridColumn:'1 / -1' }}>
            <label style={lbl}>Shelf Location</label>
            <input style={inp} placeholder="e.g. Aisle 3, Shelf B"
              value={form.shelf_location} onChange={e => handle('shelf_location', e.target.value)} />
          </div>
        </div>

        {error && <div className="error" style={{ marginTop:10 }}>{error}</div>}

        <div style={{ display:'flex', gap:10, marginTop:18, justifyContent:'flex-end' }}>
          <button onClick={onClose}
            style={{ padding:'8px 18px', borderRadius:6, border:'1px solid #ddd', cursor:'pointer', background:'#fff' }}>
            Cancel
          </button>
          <button className="btn" onClick={submit} disabled={saving}>
            {saving ? 'Saving…' : `💾 Save ${form.quantity} units`}
          </button>
        </div>
      </div>
    </div>
  );
}

const overlay = { position:'fixed', inset:0, background:'rgba(0,0,0,0.5)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000 };
const modal   = { background:'#fff', borderRadius:12, padding:24, width:'100%', maxWidth:500, boxShadow:'0 8px 40px rgba(0,0,0,0.2)', maxHeight:'92vh', overflowY:'auto' };
const lbl     = { display:'block', fontSize:12, fontWeight:600, color:'#555', marginBottom:4 };
const inp     = { width:'100%', padding:'7px 10px', borderRadius:6, border:'1px solid #ddd', fontSize:13, boxSizing:'border-box' };


// ── Progress panel shown while batches are running ───────────────
const STATUS_MSGS = [
  'Scanning product labels…',
  'Reading brand names…',
  'Checking package colours…',
  'Matching shelf positions…',
  'Cross-referencing product database…',
  'Estimating prices…',
  'Grouping similar items…',
  'Almost there…',
];

const PROVIDER_LABELS = {
  openai:       { label: 'GPT-4o',        color: '#16a34a', icon: '🤖' },
  gemini:       { label: 'Gemini',         color: '#0891b2', icon: '✨' },
  groq:         { label: 'Groq Llama 4',  color: '#7c3aed', icon: '⚡' },
  'rule-based': { label: 'Rule-based',    color: '#d97706', icon: '📐' },
};

function IdentifyProgress({ totalBatches, completedBatches, totalItems, foundItems, provider, recentNames, imageSrc, recentBboxes }) {
  const [msgIdx, setMsgIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setMsgIdx(i => (i + 1) % STATUS_MSGS.length), 2200);
    return () => clearInterval(t);
  }, []);

  const pct   = totalBatches ? Math.round((completedBatches / totalBatches) * 100) : 0;
  const pInfo = PROVIDER_LABELS[provider] || PROVIDER_LABELS['rule-based'];

  return (
    <div className="card" style={{ background:'linear-gradient(135deg,#0f172a,#1e1b4b)', color:'#fff', border:'none' }}>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:18 }}>
        <div>
          <div style={{ fontWeight:700, fontSize:17, letterSpacing:0.3 }}>
            🔍 Identifying Products with AI
          </div>
          <div style={{ fontSize:12, color:'#94a3b8', marginTop:3 }}>
            {STATUS_MSGS[msgIdx]}
          </div>
        </div>
        {provider && (
          <div style={{ background:'rgba(255,255,255,0.1)', borderRadius:20, padding:'5px 14px',
                        fontSize:12, fontWeight:600, color: pInfo.color, whiteSpace:'nowrap' }}>
            {pInfo.icon} {pInfo.label}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div style={{ background:'rgba(255,255,255,0.1)', borderRadius:99, height:10, marginBottom:10, overflow:'hidden' }}>
        <div style={{
          height:'100%', borderRadius:99,
          background:'linear-gradient(90deg,#6366f1,#8b5cf6,#a78bfa)',
          width:`${pct}%`,
          transition:'width 0.6s cubic-bezier(0.4,0,0.2,1)',
          boxShadow:'0 0 12px rgba(139,92,246,0.7)',
        }} />
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:12, color:'#94a3b8', marginBottom:18 }}>
        <span>Batch {completedBatches} of {totalBatches}</span>
        <span style={{ fontWeight:700, color:'#a78bfa' }}>{pct}%</span>
      </div>

      {/* Stats row */}
      <div style={{ display:'flex', gap:12, marginBottom:18, flexWrap:'wrap' }}>
        {[
          { label:'Total items',  value: totalItems,  icon:'📦' },
          { label:'Identified',   value: foundItems,  icon:'✅' },
          { label:'Remaining',    value: totalItems - foundItems, icon:'⏳' },
        ].map(s => (
          <div key={s.label} style={{ flex:'1 1 80px', background:'rgba(255,255,255,0.07)',
                borderRadius:10, padding:'10px 14px', textAlign:'center' }}>
            <div style={{ fontSize:20 }}>{s.icon}</div>
            <div style={{ fontSize:20, fontWeight:800, marginTop:2 }}>{s.value}</div>
            <div style={{ fontSize:10, color:'#94a3b8', marginTop:1 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Live thumbnail strip — last identified crops */}
      {recentBboxes?.length > 0 && imageSrc && (
        <div>
          <div style={{ fontSize:11, color:'#64748b', marginBottom:8, fontWeight:600, textTransform:'uppercase', letterSpacing:1 }}>
            Recently identified
          </div>
          <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
            {recentBboxes.slice(-8).map((item, i) => (
              <div key={i} style={{ textAlign:'center' }}>
                <CropThumb imageSrc={imageSrc} bbox={item.bbox} size={52} />
                <div style={{ fontSize:9, color:'#94a3b8', marginTop:3, maxWidth:52,
                              overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  {(item.name || 'Unknown').split(' ').slice(0,2).join(' ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── YOLO scanning overlay ────────────────────────────────────────
const SCAN_STEPS = [
  { icon: '📤', label: 'Uploading image…'            },
  { icon: '🔍', label: 'Loading YOLOv8 model…'       },
  { icon: '🧠', label: 'Running object detection…'   },
  { icon: '📐', label: 'Drawing bounding boxes…'     },
  { icon: '✅', label: 'Finalising results…'          },
];

function ScanningOverlay({ imageSrc }) {
  const [step,    setStep]    = useState(0);
  const [dotCount, setDots]   = useState(0);

  useEffect(() => {
    const t1 = setInterval(() => setStep(s  => Math.min(s  + 1, SCAN_STEPS.length - 1)), 1400);
    const t2 = setInterval(() => setDots(d  => (d + 1) % 4), 450);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, []);

  const dots = '.'.repeat(dotCount);

  return (
    <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', userSelect: 'none' }}>
      {/* Blurred preview image */}
      <img
        src={imageSrc}
        alt="scanning"
        style={{
          display: 'block', width: '100%', maxHeight: 320,
          objectFit: 'cover', filter: 'brightness(0.45) blur(1px)',
          borderRadius: 14,
        }}
      />

      {/* Sweeping scan line */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        overflow: 'hidden', borderRadius: 14, pointerEvents: 'none',
      }}>
        <div style={{
          position: 'absolute', left: 0, right: 0, height: 3,
          background: 'linear-gradient(90deg,transparent,#6366f1,#a78bfa,#6366f1,transparent)',
          boxShadow: '0 0 18px 6px rgba(139,92,246,0.7)',
          animation: 'scanLine 1.8s ease-in-out infinite',
        }} />
        {/* Horizontal grid lines */}
        {[20, 40, 60, 80].map(pct => (
          <div key={pct} style={{
            position: 'absolute', top: `${pct}%`, left: 0, right: 0,
            height: 1, background: 'rgba(99,102,241,0.15)',
          }} />
        ))}
        {/* Vertical grid lines */}
        {[25, 50, 75].map(pct => (
          <div key={pct} style={{
            position: 'absolute', left: `${pct}%`, top: 0, bottom: 0,
            width: 1, background: 'rgba(99,102,241,0.15)',
          }} />
        ))}
        {/* Pulsing detection box hints */}
        {[
          { top:'15%', left:'12%', w:22, h:28 },
          { top:'30%', left:'55%', w:18, h:22 },
          { top:'55%', left:'28%', w:20, h:25 },
          { top:'20%', left:'72%', w:16, h:20 },
          { top:'65%', left:'68%', w:19, h:24 },
        ].map((b, i) => (
          <div key={i} style={{
            position: 'absolute', top: b.top, left: b.left,
            width: `${b.w}%`, height: `${b.h}%`,
            border: '1.5px solid rgba(99,102,241,0.55)',
            borderRadius: 4,
            animation: `pulse ${1.2 + i * 0.3}s ease-in-out ${i * 0.25}s infinite`,
          }} />
        ))}
      </div>

      {/* Centre overlay card */}
      <div style={{
        position: 'absolute', inset: 0, display: 'flex',
        flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 18,
      }}>
        {/* Spinner ring */}
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          border: '3px solid rgba(255,255,255,0.12)',
          borderTop: '3px solid #8b5cf6',
          borderRight: '3px solid #6366f1',
          animation: 'spin 0.9s linear infinite',
          flexShrink: 0,
        }} />

        {/* Status text */}
        <div style={{
          background: 'rgba(15,23,42,0.85)',
          backdropFilter: 'blur(8px)',
          borderRadius: 12, padding: '14px 28px',
          textAlign: 'center', minWidth: 240,
          border: '1px solid rgba(99,102,241,0.35)',
        }}>
          <div style={{ fontSize: 22, marginBottom: 6 }}>
            {SCAN_STEPS[step].icon}
          </div>
          <div style={{ color: '#fff', fontWeight: 700, fontSize: 14 }}>
            {SCAN_STEPS[step].label}{dots}
          </div>
          <div style={{ color: '#94a3b8', fontSize: 11, marginTop: 4 }}>
            YOLOv8 object detection
          </div>
        </div>

        {/* Step dots */}
        <div style={{ display: 'flex', gap: 8 }}>
          {SCAN_STEPS.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 20 : 8, height: 8,
              borderRadius: 99,
              background: i <= step ? '#8b5cf6' : 'rgba(255,255,255,0.2)',
              transition: 'width 0.3s, background 0.3s',
            }} />
          ))}
        </div>
      </div>

      {/* Keyframes injected once */}
      <style>{`
        @keyframes scanLine {
          0%   { top: -4px; }
          50%  { top: calc(100% + 4px); }
          100% { top: -4px; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50%      { opacity: 0.9; transform: scale(1.03); }
        }
      `}</style>
    </div>
  );
}

// ── Main Detection page ──────────────────────────────────────────
export default function Detection() {
  const [dragging,      setDragging]      = useState(false);
  const [result,        setResult]        = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);   // 0=idle, 1,2,3=running
  const [pipelineStats, setPipelineStats] = useState(null);
  const [enriched,      setEnriched]      = useState(null); // pipeline-enriched detections
  const [identifying,   setIdentifying]   = useState(false);
  const [groups,        setGroups]        = useState(null);
  const [savedNames,    setSavedNames]    = useState({});
  const [modalGroup,      setModalGroup]      = useState(null);
  const [showCamera,      setShowCamera]      = useState(false);
  const [libraryModal,    setLibraryModal]    = useState(null); // {bbox, index}
  const [savedToLibrary,  setSavedToLibrary]  = useState({});   // name -> 'saving'|'done'|'error'
  const [bulkSave,        setBulkSave]        = useState(null); // {done, total, type, currentName}
  const [error,           setError]           = useState('');
  const [preview,         setPreview]         = useState(null);
  const [progress,      setProgress]      = useState(null);
  const inputRef       = useRef();
  const mobileInputRef = useRef();

  const handleFile = async (file) => {
    if (!file.type.startsWith('image/')) { setError('Please upload an image file.'); return; }
    setError('');
    setResult(null); setGroups(null); setSavedNames({}); setSavedToLibrary({});
    setProgress(null); setEnriched(null); setPipelineStats(null); setPipelineStage(0);
    setPreview(URL.createObjectURL(file));
    setLoading(true);

    let uploadResult = null;
    try {
      // Stage 1: YOLO
      setPipelineStage(1);
      const res = await detectionAPI.upload(file);
      uploadResult = res.data;
      setResult(uploadResult);
    } catch (e) {
      setError(e.response?.data?.detail || 'Detection failed. Is the backend running?');
      setLoading(false);
      setPipelineStage(0);
      return;
    }

    // Stage 2 + 3: CLIP pipeline (runs immediately after YOLO)
    try {
      setPipelineStage(2);
      await new Promise(r => setTimeout(r, 300)); // brief pause so stage 2 badge animates
      setPipelineStage(3);
      const pr = await detectionAPI.pipeline(uploadResult.event_id, uploadResult.detections);
      setEnriched(pr.data.detections);
      setPipelineStats(pr.data.pipeline_stats);
    } catch (e) {
      // Pipeline failure is non-fatal — still show YOLO results
      console.warn('Pipeline (Stage 2/3) failed:', e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
      setPipelineStage(0);
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleIdentifyAll = async () => {
    if (!result) return;
    setIdentifying(true);
    setProgress(null);

    const BATCH       = 10;
    const detections  = result.detections;
    const totalBatches = Math.ceil(detections.length / BATCH);
    let allItems       = [];
    let provider       = '';

    setProgress({ total: totalBatches, done: 0, foundItems: 0, provider: '', recent: [] });

    try {
      for (let b = 0; b < totalBatches; b++) {
        const slice = detections.slice(b * BATCH, (b + 1) * BATCH);
        const res   = await detectionAPI.identifyBatch(result.event_id, slice, b * BATCH, provider);
        const { items, provider_used } = res.data;
        provider  = provider_used;
        allItems  = [...allItems, ...items];

        // Build recent thumbnail data (last 8 identified)
        const recentItems = allItems.slice(-8).map(item => ({
          name: item.name,
          bbox: detections[item.index - 1]?.bbox || [0,0,50,50],
        }));

        setProgress({
          total:      totalBatches,
          done:       b + 1,
          foundItems: allItems.length,
          provider:   provider_used,
          recent:     recentItems,
        });
      }

      // Group results client-side (same logic as backend)
      const idMap  = {};
      allItems.forEach(item => { idMap[item.index] = item; });

      const groupMap = {};
      detections.forEach((d, idx) => {
        const info = idMap[idx + 1] || {};
        const name = info.name || `Unknown Product #${idx + 1}`;
        const key  = name.toLowerCase().trim();
        if (!groupMap[key]) {
          groupMap[key] = {
            name,
            brand:           info.brand || '',
            category:        info.category || 'General',
            estimated_price: info.estimated_price || 0,
            sku:             info.sku || `SKU-${idx + 1}`,
            count:           0,
            confidences:     [],
            indices:         [],
            first_bbox:      d.bbox,
          };
        }
        groupMap[key].count++;
        groupMap[key].confidences.push(d.confidence || 0);
        groupMap[key].indices.push(idx);
      });

      const grouped = Object.values(groupMap).map(g => ({
        ...g,
        avg_confidence: parseFloat((g.confidences.reduce((a,b)=>a+b,0)/g.confidences.length).toFixed(3)),
      })).sort((a, b) => b.count - a.count);

      setGroups(grouped);
    } catch (e) {
      setError(e.response?.data?.detail || 'Identification failed.');
    } finally {
      setIdentifying(false);
      setProgress(null);
    }
  };

  const handleAddAll = async () => {
    if (!groups) return;
    const pending = groups.filter(g => !savedNames[g.name]);
    if (!pending.length) return;
    setBulkSave({ done: 0, total: pending.length, type: 'db', currentName: pending[0]?.name });
    let done = 0;
    for (const g of pending) {
      setBulkSave(s => ({ ...s, currentName: g.name }));
      try {
        const res = await detectionAPI.saveProduct({
          name: g.name, sku: g.sku, category: g.category,
          price: parseFloat(g.estimated_price) || 0,
          quantity: g.count,
          low_stock_threshold: Math.max(5, Math.round(g.count * 0.3)),
          shelf_location: '',
        });
        setSavedNames(s => ({ ...s, [g.name]: res.data }));
      } catch { /* skip duplicates */ }
      done++;
      setBulkSave(s => ({ ...s, done }));
    }
    setBulkSave(null);
  };

  const onSaved = (name, data) => setSavedNames(s => ({ ...s, [name]: data }));

  // Save an LLM-identified group to the CLIP product library.
  // We save up to 3 crops (different bounding boxes) from the group so that
  // Stage 3 gets multiple reference angles, improving future match accuracy.
  const handleSaveToLibrary = async (group) => {
    if (!result || savedToLibrary[group.name]) return;
    setSavedToLibrary(s => ({ ...s, [group.name]: 'saving' }));
    try {
      // Collect bboxes: first_bbox + up to 2 more from g.indices
      const bboxes = [group.first_bbox];
      if (group.indices && result.detections) {
        for (const idx of group.indices.slice(1, 3)) {
          const det = result.detections[idx];
          if (det?.bbox) bboxes.push(det.bbox);
        }
      }
      // Save each bbox as a separate reference image for this product
      for (const bbox of bboxes) {
        await detectionAPI.addToLibrary(result.event_id, bbox, group.name);
      }
      setSavedToLibrary(s => ({ ...s, [group.name]: 'done' }));
    } catch (e) {
      setSavedToLibrary(s => ({ ...s, [group.name]: 'error' }));
    }
  };

  const handleSaveAllToLibrary = async () => {
    if (!groups) return;
    const pending = groups.filter(g => savedToLibrary[g.name] !== 'done');
    if (!pending.length) return;
    setBulkSave({ done: 0, total: pending.length, type: 'library', currentName: pending[0]?.name });
    let done = 0;
    for (const g of pending) {
      setBulkSave(s => ({ ...s, currentName: g.name }));
      await handleSaveToLibrary(g);
      done++;
      setBulkSave(s => ({ ...s, done }));
    }
    setBulkSave(null);
  };

  const savedCount    = Object.keys(savedNames).length;
  const totalDetected = result?.total_detected || 0;
  const uniqueProducts = groups?.length || 0;
  const avgConf = result?.detections?.length
    ? (result.detections.reduce((s, d) => s + d.confidence, 0) / result.detections.length * 100).toFixed(1)
    : 0;

  // After adding a crop to the library, update local enriched state so the row shows "Known"
  const handleLibrarySaved = (productName) => {
    setLibraryModal(null);
    if (enriched && libraryModal) {
      setEnriched(prev => prev.map((d, i) =>
        i === libraryModal.index
          ? { ...d, matched_product: productName, match_confidence: 1.0, stage: 3 }
          : d
      ));
    }
  };

  return (
    <div className="page">
      <div className="page-title">🔍 Product Detection</div>

      {/* Upload / Camera */}
      <div className="card">
        <div className="card-title">Scan Shelf</div>

        {/* Drag-drop zone */}
        {loading && preview ? (
          <ScanningOverlay imageSrc={preview} />
        ) : (
          <div
            className={`drop-zone ${dragging ? 'over' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            style={{ cursor: 'default' }}
          >
            {preview
              ? <img src={preview} alt="preview"
                  style={{ maxHeight: 200, maxWidth: '100%', borderRadius: 8 }} />
              : <>
                  <div style={{ fontSize: 44, marginBottom: 8 }}>🛒</div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>Drag &amp; drop a shelf image here</div>
                  <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>JPG, PNG — max 20 MB</div>
                </>
            }
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
          <button className="btn"
            disabled={loading}
            style={{ flex: '1 1 140px', display: 'flex', alignItems: 'center',
                     justifyContent: 'center', gap: 8, padding: '11px 0',
                     opacity: loading ? 0.5 : 1, cursor: loading ? 'default' : 'pointer' }}
            onClick={() => !loading && inputRef.current.click()}>
            📁 Upload Image
          </button>
          <button className="btn"
            disabled={loading}
            style={{ flex: '1 1 140px', display: 'flex', alignItems: 'center',
                     justifyContent: 'center', gap: 8, padding: '11px 0',
                     background: 'linear-gradient(135deg,#1a237e,#0288d1)',
                     opacity: loading ? 0.5 : 1, cursor: loading ? 'default' : 'pointer' }}
            onClick={() => {
              if (loading) return;
              if (/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
                mobileInputRef.current.click();
              } else {
                setShowCamera(true);
              }
            }}>
            📷 Use Camera
          </button>
        </div>

        {/* Hidden inputs */}
        <input ref={inputRef} type="file" accept="image/*" style={{ display:'none' }}
          onChange={e => { if (e.target.files[0]) handleFile(e.target.files[0]); }} />
        {/* Mobile camera input — capture="environment" opens rear camera directly */}
        <input ref={mobileInputRef} type="file" accept="image/*" capture="environment"
          style={{ display:'none' }}
          onChange={e => { if (e.target.files[0]) handleFile(e.target.files[0]); }} />

        {error && !loading && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {/* Camera modal */}
      {showCamera && (
        <CameraModal
          onCapture={file => { setShowCamera(false); handleFile(file); }}
          onClose={() => setShowCamera(false)}
        />
      )}

      {/* Pipeline banner — shown while stages 2/3 run or after completion */}
      {(pipelineStage > 0 || pipelineStats) && (
        <PipelineBanner
          currentStage={pipelineStage > 0 ? pipelineStage : 4}
          stats={pipelineStats}
        />
      )}

      {/* CLIP not ready warning */}
      {pipelineStats && pipelineStats.clip_ready === false && (
        <div style={{
          background:'#fff7ed', border:'2px solid #f97316', borderRadius:10,
          padding:'12px 16px', marginBottom:16, display:'flex', gap:12, alignItems:'flex-start',
        }}>
          <span style={{ fontSize:20 }}>⚠️</span>
          <div>
            <div style={{ fontWeight:700, color:'#c2410c', fontSize:14, marginBottom:4 }}>
              CLIP Model Not Loaded — Stage 2 &amp; 3 are unavailable
            </div>
            <div style={{ fontSize:13, color:'#7c2d12', lineHeight:1.5 }}>
              Category classification and SKU matching require the <b>transformers</b> package.
              Run this in your backend directory, then restart the server:
            </div>
            <code style={{
              display:'inline-block', marginTop:6, padding:'4px 10px',
              background:'#1e293b', color:'#fbbf24', borderRadius:6, fontSize:12,
            }}>
              pip install transformers&gt;=4.40.0
            </code>
            {pipelineStats.clip_error && (
              <div style={{ marginTop:6, fontSize:11, color:'#9a3412', fontFamily:'monospace' }}>
                Error: {pipelineStats.clip_error}
              </div>
            )}
          </div>
        </div>
      )}

      {result && (
        <>
          {/* Stats */}
          <div style={{ display:'flex', gap:14, flexWrap:'wrap', marginBottom:16 }}>
            {[
              { label:'Total Detected',    value: totalDetected,                         color:'#1a237e' },
              { label:'Stage 3 Matched',   value: pipelineStats?.stage3_matched ?? '—',  color:'#7c3aed' },
              { label:'Unmatched',         value: pipelineStats?.stage3_unmatched ?? '—',color:'#f59e0b' },
              { label:'Avg Confidence',    value: `${avgConf}%`,                          color:'#00897b' },
              { label:'Added to DB',       value: savedCount,                             color:'#f57c00' },
            ].map(s => (
              <div key={s.label} className="stat-card" style={{ flex:'1 1 120px' }}>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ color:s.color }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Annotated image */}
          <div className="card">
            <div className="card-title">
              Shelf View — {groups ? `${uniqueProducts} unique products` : `${totalDetected} products detected`}
            </div>
            <AnnotatedImage imageSrc={preview} detections={result.detections} groups={groups} />

            {/* Identify unmatched via AI — only for items not already matched in Stage 3 */}
            {!groups && !identifying && (
              <div style={{ marginTop:14, display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
                <button className="btn" onClick={handleIdentifyAll}
                  style={{ display:'flex', alignItems:'center', gap:8,
                           background:'linear-gradient(135deg,#6366f1,#8b5cf6)',
                           padding:'10px 22px', fontSize:14 }}>
                  <span>✨</span>
                  {pipelineStats?.stage3_unmatched
                    ? `Identify ${pipelineStats.stage3_unmatched} Unmatched with AI`
                    : 'Identify & Group with AI'}
                </button>
                {pipelineStats && (
                  <span style={{ fontSize:12, color:'#64748b' }}>
                    {pipelineStats.stage3_matched} already matched from library · {pipelineStats.library_size} products in library
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Live AI identification progress */}
          {identifying && progress && (
            <IdentifyProgress
              totalBatches={progress.total}
              completedBatches={progress.done}
              totalItems={result.detections.length}
              foundItems={progress.foundItems}
              provider={progress.provider}
              recentBboxes={progress.recent}
              imageSrc={preview}
            />
          )}

          {/* Enriched pipeline results table — shows immediately after pipeline */}
          {enriched && !groups && (
            <div className="card">
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
                <div className="card-title" style={{ margin:0 }}>
                  Pipeline Results — {enriched.length} detections
                </div>
                <div style={{ fontSize:12, color:'#64748b' }}>
                  ✅ Stage 3 matched: <b style={{ color:'#16a34a' }}>{pipelineStats?.stage3_matched}</b>
                  &nbsp;·&nbsp;
                  ❓ Unmatched: <b style={{ color:'#d97706' }}>{pipelineStats?.stage3_unmatched}</b>
                </div>
              </div>
              <div style={{ overflowX:'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Preview</th>
                      <th>Stage 2 — Category</th>
                      <th>Stage 3 — Matched Product</th>
                      <th>Match Conf.</th>
                      <th>YOLO Conf.</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {enriched.map((d, i) => (
                      <tr key={i}>
                        <td><CropThumb imageSrc={preview} bbox={d.bbox} size={52} /></td>
                        <td>
                          <span style={{
                            background:'#ede9fe', color:'#6d28d9',
                            borderRadius:99, padding:'3px 10px',
                            fontSize:12, fontWeight:600,
                          }}>
                            {d.category}
                          </span>
                          <div style={{ fontSize:10, color:'#94a3b8', marginTop:2 }}>
                            {(d.category_confidence * 100).toFixed(0)}% confidence
                          </div>
                        </td>
                        <td>
                          {d.matched_product
                            ? <span style={{ fontWeight:600, color:'#1e293b', fontSize:13 }}>{d.matched_product}</span>
                            : d.off_suggestions?.length > 0
                              ? (
                                <div>
                                  <div style={{ fontSize:10, color:'#7c3aed', fontWeight:700, marginBottom:4 }}>
                                    🌐 Open Food Facts suggestions:
                                  </div>
                                  {d.off_suggestions.map((s, si) => (
                                    <div key={si} style={{ display:'flex', alignItems:'center', gap:6, marginBottom:3 }}>
                                      {s.image_url && (
                                        <img src={s.image_url} alt="" style={{ width:24, height:24, objectFit:'contain', borderRadius:3 }} />
                                      )}
                                      <div>
                                        <a href={s.off_url} target="_blank" rel="noreferrer"
                                           style={{ fontSize:11, color:'#1d4ed8', fontWeight:600, textDecoration:'none' }}>
                                          {s.name}
                                        </a>
                                        {s.brand && <span style={{ fontSize:10, color:'#64748b' }}> · {s.brand}</span>}
                                        {s.nutriscore && (
                                          <span style={{
                                            marginLeft:4, padding:'1px 5px', borderRadius:3, fontSize:9, fontWeight:700,
                                            background: s.nutriscore === 'a' ? '#16a34a' : s.nutriscore === 'b' ? '#65a30d' : s.nutriscore === 'c' ? '#ca8a04' : '#dc2626',
                                            color:'white',
                                          }}>
                                            {s.nutriscore.toUpperCase()}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )
                              : <span style={{ color:'#94a3b8', fontSize:12 }}>Not in library</span>
                          }
                        </td>
                        <td>
                          {d.match_confidence
                            ? <span style={{ fontWeight:700, color:'#16a34a' }}>{(d.match_confidence * 100).toFixed(0)}%</span>
                            : <span style={{ color:'#e2e8f0' }}>—</span>}
                        </td>
                        <td style={{ color:'#64748b', fontSize:13 }}>
                          {(d.confidence * 100).toFixed(0)}%
                        </td>
                        <td>
                          {d.matched_product ? (
                            <span style={{ fontSize:11, color:'#16a34a', fontWeight:600 }}>✅ Known</span>
                          ) : (
                            <button
                              onClick={() => setLibraryModal({ bbox: d.bbox, index: i })}
                              style={{
                                padding:'4px 10px', borderRadius:6, border:'1px solid #c7d2fe',
                                background:'#eef2ff', color:'#4338ca', cursor:'pointer',
                                fontSize:11, fontWeight:600,
                              }}
                            >
                              + Add to Library
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Grouped product table — shown only after identification */}
          {groups && (
            <div className="card">
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14, flexWrap:'wrap', gap:8 }}>
                <div className="card-title" style={{ margin:0 }}>
                  {uniqueProducts} Unique Products Identified
                </div>
                <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                  {/* Save all to CLIP library */}
                  {(() => {
                    const libDoneCount = Object.values(savedToLibrary).filter(v => v === 'done').length;
                    const allLibSaved  = libDoneCount === groups.length;
                    const isSavingLib  = bulkSave?.type === 'library';
                    return (
                      <button className="btn"
                        style={{
                          background: allLibSaved ? '#7c3aed' : '#6d28d9', fontSize:12,
                          display:'flex', alignItems:'center', gap:6,
                          opacity: (allLibSaved || isSavingLib) ? 0.7 : 1,
                        }}
                        onClick={handleSaveAllToLibrary}
                        disabled={allLibSaved || isSavingLib}>
                        {allLibSaved ? '✅ All in Library'
                          : isSavingLib ? `📚 ${bulkSave.done}/${bulkSave.total} saved…`
                          : `📚 Save All to Library (${groups.length - libDoneCount})`}
                      </button>
                    );
                  })()}
                  {/* Save all to inventory DB */}
                  {(() => {
                    const allInDB    = savedCount === groups.length;
                    const isSavingDB = bulkSave?.type === 'db';
                    return (
                      <button className="btn"
                        style={{
                          background: allInDB ? '#16a34a' : undefined, fontSize:12,
                          display:'flex', alignItems:'center', gap:6,
                          opacity: (allInDB || isSavingDB) ? 0.7 : 1,
                        }}
                        onClick={handleAddAll}
                        disabled={allInDB || isSavingDB}>
                        {allInDB ? '✅ All in DB'
                          : isSavingDB ? `💾 ${bulkSave.done}/${bulkSave.total} saved…`
                          : `💾 Add All to DB (${groups.length - savedCount})`}
                      </button>
                    );
                  })()}
                </div>
              </div>

              {/* Bulk save progress bar */}
              {bulkSave && (
                <BulkSaveProgress
                  done={bulkSave.done}
                  total={bulkSave.total}
                  type={bulkSave.type}
                  currentName={bulkSave.currentName}
                />
              )}

              <table>
                <thead>
                  <tr>
                    <th>Preview</th>
                    <th>Product Name</th>
                    <th>Category</th>
                    <th>Count</th>
                    <th>Avg Conf.</th>
                    <th>Est. Price</th>
                    <th>Library</th>
                    <th>Inventory</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g, i) => {
                    const isSaved   = !!savedNames[g.name];
                    const confColor = g.avg_confidence >= 0.8 ? '#16a34a' : g.avg_confidence >= 0.6 ? '#d97706' : '#dc2626';
                    return (
                      <tr key={i} style={{ background: isSaved ? '#f0fdf4' : undefined }}>
                        <td><CropThumb imageSrc={preview} bbox={g.first_bbox} size={52} /></td>
                        <td>
                          <div style={{ fontWeight:600, fontSize:13 }}>{g.name}</div>
                          {g.brand && <div style={{ fontSize:11, color:'#888' }}>{g.brand}</div>}
                        </td>
                        <td>
                          <span style={{ background:'#ede9fe', color:'#6d28d9', borderRadius:10,
                                         padding:'2px 10px', fontSize:12, fontWeight:600 }}>
                            {g.category}
                          </span>
                        </td>
                        <td>
                          <span style={{ background:'#dbeafe', color:'#1d4ed8', borderRadius:10,
                                         padding:'2px 10px', fontSize:13, fontWeight:700 }}>
                            {g.count} units
                          </span>
                        </td>
                        <td style={{ color:confColor, fontWeight:700 }}>
                          {(g.avg_confidence * 100).toFixed(1)}%
                        </td>
                        <td style={{ fontSize:13 }}>
                          {g.estimated_price ? `$${Number(g.estimated_price).toFixed(2)}` : '—'}
                        </td>
                        {/* Library column */}
                        <td>
                          {savedToLibrary[g.name] === 'done'
                            ? (
                              <span style={{
                                display:'inline-flex', alignItems:'center', gap:4,
                                color:'#7c3aed', fontWeight:700, fontSize:12,
                                background:'#f5f3ff', padding:'3px 9px', borderRadius:99,
                              }}>✅ Saved</span>
                            )
                            : savedToLibrary[g.name] === 'saving'
                            ? (
                              <span style={{ display:'inline-flex', alignItems:'center', gap:5, fontSize:12, color:'#6d28d9' }}>
                                <span style={{
                                  width:12, height:12, border:'2px solid #c4b5fd',
                                  borderTopColor:'#7c3aed', borderRadius:'50%',
                                  display:'inline-block', animation:'spin 0.7s linear infinite',
                                }}/>
                                Saving…
                              </span>
                            )
                            : savedToLibrary[g.name] === 'error'
                            ? <span style={{ color:'#dc2626', fontSize:12 }} title="CLIP unavailable?">❌ Failed</span>
                            : (
                              <button
                                onClick={() => handleSaveToLibrary(g)}
                                disabled={!!bulkSave}
                                style={{
                                  padding:'4px 10px', borderRadius:6, border:'1px solid #c4b5fd',
                                  background:'#f5f3ff', color:'#6d28d9', cursor: bulkSave ? 'default' : 'pointer',
                                  fontSize:11, fontWeight:600, opacity: bulkSave ? 0.5 : 1,
                                }}
                                title={`Save up to ${Math.min(g.count, 3)} crop(s) as reference images`}
                              >
                                📚 Save
                              </button>
                            )
                          }
                        </td>
                        {/* Inventory column */}
                        <td>
                          {isSaved
                            ? (
                              <span style={{
                                display:'inline-flex', alignItems:'center', gap:4,
                                color:'#16a34a', fontWeight:700, fontSize:12,
                                background:'#f0fdf4', padding:'3px 9px', borderRadius:99,
                              }}>✅ In DB</span>
                            )
                            : <button className="btn" style={{ padding:'4px 14px', fontSize:12, opacity: bulkSave?.type==='db' ? 0.5 : 1 }}
                                disabled={bulkSave?.type === 'db'}
                                onClick={() => setModalGroup(g)}>+ Add</button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Inventory auto-updates */}
          {result.inventory_updates.length > 0 && (
            <div className="card">
              <div className="card-title">📦 Auto Inventory Updates</div>
              <table>
                <thead><tr><th>SKU</th><th>Product</th><th>Old Qty</th><th>New Qty</th></tr></thead>
                <tbody>
                  {result.inventory_updates.map((u, i) => (
                    <tr key={i}>
                      <td>{u.sku}</td><td>{u.name}</td><td>{u.old_quantity}</td>
                      <td><strong style={{ color: u.new_quantity < u.old_quantity ? '#dc2626' : '#16a34a' }}>
                        {u.new_quantity}
                      </strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Add-to-DB modal */}
      {modalGroup && (
        <AddToDBModal
          group={modalGroup}
          imageSrc={preview}
          onSave={onSaved}
          onClose={() => setModalGroup(null)}
        />
      )}

      {/* Add-to-library modal */}
      {libraryModal && result && (
        <AddToLibraryModal
          bbox={libraryModal.bbox}
          eventId={result.event_id}
          onDone={handleLibrarySaved}
          onClose={() => setLibraryModal(null)}
        />
      )}
    </div>
  );
}

