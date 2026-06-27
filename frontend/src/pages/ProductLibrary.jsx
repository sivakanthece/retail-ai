import React, { useState, useEffect, useRef } from 'react';
import { libraryAPI } from '../services/api';

const STAGE_COLORS = {
  ready:      { bg: '#dcfce7', color: '#15803d', label: '✅ CLIP Ready' },
  not_loaded: { bg: '#fef3c7', color: '#d97706', label: '⏳ Not loaded yet' },
  error:      { bg: '#fee2e2', color: '#dc2626', label: '❌ Unavailable' },
  unknown:    { bg: '#f1f5f9', color: '#64748b', label: '❓ Unknown' },
};

function StageCard({ stage, title, desc, status }) {
  const s = STAGE_COLORS[status] || STAGE_COLORS.unknown;
  return (
    <div style={{
      background: '#fff', borderRadius: 14, padding: '18px 20px',
      boxShadow: '0 2px 12px rgba(99,102,241,0.07)',
      border: '1px solid #e2e8f0', flex: '1 1 260px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ fontSize: 28 }}>{stage === 1 ? '🔲' : stage === 2 ? '🏷️' : '🔎'}</div>
        <span style={{
          padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700,
          background: s.bg, color: s.color,
        }}>{s.label}</span>
      </div>
      <div style={{ fontWeight: 700, fontSize: 15, color: '#1e293b', marginBottom: 4 }}>
        Stage {stage} — {title}
      </div>
      <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>{desc}</div>
    </div>
  );
}

function ProductCard({ product_name, refs, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{
      background: '#fff', borderRadius: 14, overflow: 'hidden',
      boxShadow: '0 2px 12px rgba(99,102,241,0.07)',
      border: '1px solid #e2e8f0',
    }}>
      {/* Header */}
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', cursor: 'pointer',
          background: expanded ? '#f8faff' : '#fff',
        }}
        onClick={() => setExpanded(e => !e)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, overflow: 'hidden',
            border: '1px solid #e2e8f0', flexShrink: 0,
          }}>
            <img
              src={refs[0]?.image_url}
              alt={product_name}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={e => { e.target.style.display = 'none'; }}
            />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#1e293b' }}>{product_name}</div>
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
              {refs.length} reference image{refs.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700,
            background: refs.length >= 3 ? '#dcfce7' : refs.length >= 2 ? '#fef3c7' : '#fee2e2',
            color: refs.length >= 3 ? '#15803d' : refs.length >= 2 ? '#d97706' : '#dc2626',
          }}>
            {refs.length >= 3 ? 'Good coverage' : refs.length >= 2 ? 'Moderate' : 'Needs more refs'}
          </span>
          <span style={{ fontSize: 16, color: '#94a3b8' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '0 18px 18px', borderTop: '1px solid #f1f5f9' }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 12 }}>
            {refs.map(ref => (
              <div key={ref.id} style={{ position: 'relative' }}>
                <img
                  src={ref.image_url}
                  alt="ref"
                  style={{
                    width: 80, height: 80, objectFit: 'cover',
                    borderRadius: 10, border: '1px solid #e2e8f0', display: 'block',
                  }}
                  onError={e => { e.target.src = ''; }}
                />
                <button
                  onClick={() => onDelete(ref.id)}
                  style={{
                    position: 'absolute', top: -6, right: -6,
                    width: 20, height: 20, borderRadius: '50%',
                    background: '#ef4444', border: 'none', color: '#fff',
                    fontSize: 12, cursor: 'pointer', lineHeight: 1,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >×</button>
                <div style={{ fontSize: 9, color: '#94a3b8', textAlign: 'center', marginTop: 3 }}>
                  {new Date(ref.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
          {refs.length < 3 && (
            <div style={{
              marginTop: 12, fontSize: 12, color: '#d97706',
              background: '#fefce8', padding: '8px 12px', borderRadius: 8,
              border: '1px solid #fde68a',
            }}>
              💡 Add {3 - refs.length} more reference image{3 - refs.length !== 1 ? 's' : ''} for better matching accuracy.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProductLibrary() {
  const [refs,      setRefs]      = useState([]);
  const [stats,     setStats]     = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error,     setError]     = useState('');
  const [success,   setSuccess]   = useState('');
  const [search,    setSearch]    = useState('');

  // Upload form state
  const [productName, setProductName] = useState('');
  const [file,        setFile]        = useState(null);
  const [preview,     setPreview]     = useState(null);
  const fileRef = useRef();

  const load = () => {
    setLoading(true);
    Promise.all([libraryAPI.listRefs(), libraryAPI.stats()])
      .then(([r1, r2]) => { setRefs(r1.data); setStats(r2.data); })
      .catch(() => setError('Failed to load library.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleFile = (f) => {
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const handleUpload = async () => {
    if (!file || !productName.trim()) {
      setError('Product name and image are required.');
      return;
    }
    setUploading(true); setError(''); setSuccess('');
    try {
      await libraryAPI.addRef(file, productName.trim());
      setSuccess(`✅ Added reference for "${productName.trim()}"`);
      setProductName(''); setFile(null); setPreview(null);
      load();
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await libraryAPI.deleteRef(id);
      load();
    } catch {
      setError('Delete failed.');
    }
  };

  const filtered = refs.filter(r =>
    !search || r.product_name.toLowerCase().includes(search.toLowerCase())
  );

  const clipStatus = stats?.clip_ready || 'unknown';

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1200, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 26, fontWeight: 800, color: '#1e293b', letterSpacing: '-0.5px' }}>
          🏪 Product Library
        </div>
        <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 3 }}>
          Reference images that power Stage 3 fine-grained SKU matching
        </div>
      </div>

      {/* Pipeline stages info */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 24, flexWrap: 'wrap' }}>
        <StageCard
          stage={1} title="Object Detection" status="ready"
          desc="YOLOv8 detects all products on the shelf and draws bounding boxes."
        />
        <StageCard
          stage={2} title="Category Classification" status={clipStatus}
          desc="CLIP zero-shot assigns each crop to a broad retail category (Beverages, Snacks, etc.)."
        />
        <StageCard
          stage={3} title="SKU Matching" status={clipStatus}
          desc="CLIP embeddings are compared against this library. Add more reference images for better accuracy."
        />
      </div>

      {/* Stats bar */}
      {stats && (
        <div style={{
          background: '#fff', borderRadius: 14, padding: '14px 24px',
          boxShadow: '0 2px 12px rgba(99,102,241,0.07)', border: '1px solid #e2e8f0',
          display: 'flex', gap: 32, alignItems: 'center', marginBottom: 24, flexWrap: 'wrap',
        }}>
          {[
            { icon: '📦', label: 'Unique Products', value: stats.unique_products },
            { icon: '🖼️', label: 'Total References', value: stats.total_references },
            { icon: '🎯', label: 'Avg per Product',
              value: stats.unique_products
                ? (stats.total_references / stats.unique_products).toFixed(1)
                : '—' },
          ].map(s => (
            <div key={s.label}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2 }}>{s.icon} {s.label}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#1e293b' }}>{s.value}</div>
            </div>
          ))}
          <div style={{ marginLeft: 'auto' }}>
            <span style={{
              padding: '6px 16px', borderRadius: 99, fontSize: 12, fontWeight: 700,
              ...((STAGE_COLORS[clipStatus] || STAGE_COLORS.unknown)),
            }}>
              CLIP: {(STAGE_COLORS[clipStatus] || STAGE_COLORS.unknown).label}
            </span>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 20, alignItems: 'start' }}>

        {/* Upload panel */}
        <div style={{
          background: '#fff', borderRadius: 14, padding: '22px',
          boxShadow: '0 2px 12px rgba(99,102,241,0.07)', border: '1px solid #e2e8f0',
        }}>
          <div style={{ fontWeight: 700, fontSize: 15, color: '#1e293b', marginBottom: 16 }}>
            ➕ Add Reference Image
          </div>

          {/* Image drop zone */}
          <div
            onClick={() => fileRef.current.click()}
            style={{
              border: '2px dashed #c7d2fe', borderRadius: 12,
              padding: preview ? 0 : '28px 16px', textAlign: 'center',
              cursor: 'pointer', marginBottom: 14, overflow: 'hidden',
              background: '#f8faff',
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = '#6366f1'}
            onMouseLeave={e => e.currentTarget.style.borderColor = '#c7d2fe'}
          >
            {preview
              ? <img src={preview} alt="preview" style={{ width: '100%', maxHeight: 180, objectFit: 'cover', display: 'block' }} />
              : <>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>🖼️</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#6366f1' }}>Click to upload</div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                    Use a clear, frontal photo of the product label
                  </div>
                </>
            }
          </div>
          <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }}
            onChange={e => e.target.files[0] && handleFile(e.target.files[0])} />

          {/* Product name */}
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Product Name *
            </label>
            <input
              value={productName}
              onChange={e => setProductName(e.target.value)}
              placeholder="e.g. Coca-Cola Classic 330ml"
              style={{
                width: '100%', padding: '9px 12px', borderRadius: 8,
                border: '1px solid #e2e8f0', fontSize: 13, boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 14, lineHeight: 1.6 }}>
            💡 Add <b>3+ images</b> per product (different angles, lighting) for the best Stage 3 accuracy.
          </div>

          {error   && <div style={{ color: '#dc2626', fontSize: 12, marginBottom: 8 }}>{error}</div>}
          {success && <div style={{ color: '#16a34a', fontSize: 12, marginBottom: 8 }}>{success}</div>}

          <button
            onClick={handleUpload}
            disabled={uploading || !file || !productName.trim()}
            style={{
              width: '100%', padding: '11px', borderRadius: 10,
              background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
              color: '#fff', border: 'none', cursor: 'pointer',
              fontWeight: 700, fontSize: 14,
              opacity: (uploading || !file || !productName.trim()) ? 0.55 : 1,
            }}
          >
            {uploading ? '⏳ Extracting embeddings…' : '💾 Save to Library'}
          </button>
        </div>

        {/* Library list */}
        <div>
          {/* Search */}
          <div style={{ marginBottom: 14 }}>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="🔍 Search products…"
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 10,
                border: '1px solid #e2e8f0', fontSize: 13, boxSizing: 'border-box',
                background: '#fff',
              }}
            />
          </div>

          {loading
            ? <div style={{ textAlign: 'center', padding: 60, color: '#94a3b8' }}>Loading library…</div>
            : filtered.length === 0
            ? (
              <div style={{
                textAlign: 'center', padding: '60px 20px',
                background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0',
              }}>
                <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>📚</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>
                  {search ? 'No products match your search' : 'Library is empty'}
                </div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>
                  {search
                    ? 'Try a different search term.'
                    : 'Upload reference images to enable Stage 3 SKU matching. After uploading, detected products will be automatically identified.'}
                </div>
              </div>
            )
            : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {filtered.map(item => (
                  <ProductCard
                    key={item.product_name}
                    product_name={item.product_name}
                    refs={item.refs}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            )
          }
        </div>
      </div>
    </div>
  );
}
