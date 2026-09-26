import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Box, LayoutGrid, Scissors, Wrench, Sparkles } from 'lucide-react'
import { api } from '../api'

export default function Home() {
  const nav = useNavigate()
  const [projects, setProjects] = useState<any[]>([])
  const [boxes, setBoxes] = useState<any[]>([])
  const [boxTypes, setBoxTypes] = useState<any[]>([])
  const [projStats, setProjStats] = useState<Record<string, any>>({})

  useEffect(() => {
    api.projects().then(list => {
      setProjects(list)
      list.forEach(p => {
        api.projectStats(p.id).then(s => setProjStats(prev => ({ ...prev, [p.id]: s }))).catch(() => {})
      })
    }).catch(() => {})
    api.boxes().then(setBoxes).catch(() => {})
    api.boxTypes().then(r => setBoxTypes(r.boxTypes)).catch(() => {})
  }, [])

  const quick = boxTypes.slice(0, 10)
  const stats = [
    { icon: Box, label: '项目', value: projects.length, tint: '#818cf8' },
    { icon: LayoutGrid, label: '盒型实例', value: boxes.length, tint: '#c084fc' },
    { icon: Scissors, label: '支持盒型', value: boxTypes.length, tint: '#22d3ee' },
    { icon: Wrench, label: '计算工具', value: 5, tint: '#fbbf24' },
  ]

  return (
    <div>
      <div className="card anim-fadeUp" style={{
        padding: 32, marginBottom: 20, position: 'relative', overflow: 'hidden',
        border: '1px solid var(--line-strong)',
      }}>
        <div style={{ position: 'absolute', right: -40, top: -60, width: 260, height: 260, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99,102,241,.35), transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', right: 120, bottom: -90, width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(34,211,238,.2), transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'relative', maxWidth: 560 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px',
            borderRadius: 99, background: 'rgba(99,102,241,.15)', border: '1px solid rgba(99,102,241,.3)',
            fontSize: 12, color: '#a5b4fc', marginBottom: 14,
          }}>
            <Sparkles size={13} /> 参数化刀模 · 实时 3D · 生产导出
          </div>
          <h1 style={{
            fontSize: 38, fontWeight: 800, lineHeight: 1.15, letterSpacing: '-.025em', marginBottom: 12,
            background: 'linear-gradient(120deg, #fff 30%, #a5b4fc)',
            WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            从一张图纸，<br />到生产刀模
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: 14.5, lineHeight: 1.7, marginBottom: 22 }}>
            15 种盒型参数化生成，2D 展开、3D 折叠、印前预检、SVG/DXF/PDF 一键导出，AI 助手自然语言建盒。
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" onClick={() => nav('/designer')}>
              立即开始设计 <ArrowRight size={15} />
            </button>
            <button className="btn" onClick={() => nav('/ai')}>
              <Sparkles size={15} /> 试试 AI 助手
            </button>
          </div>
        </div>
      </div>

      <div className="stats">
        {stats.map((s, i) => (
          <div key={s.label} className={`card stat-card anim-fadeUp anim-fadeUp-${i + 1}`}>
            <s.icon size={22} style={{ color: s.tint, float: 'right', opacity: .8 }} />
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-3 mb">
        <div className="card anim-fadeUp anim-fadeUp-1" style={{ padding: 20 }}>
          <h3 className="section-title">快速创建盒型</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {quick.map(q => (
              <button key={q.id} className="btn btn-sm"
                onClick={() => nav(`/designer?boxType=${q.id}`)}>
                {q.label}
              </button>
            ))}
          </div>
          <div className="mt">
            <Link className="btn btn-primary btn-sm" to="/designer">进入设计器 <ArrowRight size={13} /></Link>
          </div>
        </div>

        <div className="card anim-fadeUp anim-fadeUp-2" style={{ padding: 20 }}>
          <h3 className="section-title">最近项目</h3>
          {projects.length === 0 && <div className="empty" style={{ padding: 24 }}>暂无项目</div>}
          {projects.slice(0, 4).map((p: any) => {
            const s = projStats[p.id]
            const passRate = s && s.boxCount ? Math.round(s.passedCount / s.boxCount * 100) : null
            return (
            <div key={p.id} onClick={() => nav(`/designer?project=${p.id}`)}
              style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 4px', borderBottom: '1px solid var(--line)', cursor: 'pointer', borderRadius: 6 }}>
              <span style={{ fontWeight: 500 }}>{p.name}</span>
              <span className="muted" style={{ fontSize: 12 }}>
                {s ? `${s.boxCount} 盒 · 通过率 ${passRate}%` : `${p.boxCount ?? 0} 盒`}
              </span>
            </div>
            )
          })}
          <div className="mt"><Link className="btn btn-sm" to="/projects">管理项目 <ArrowRight size={13} /></Link></div>
        </div>

        <div className="card anim-fadeUp anim-fadeUp-3" style={{ padding: 20 }}>
          <h3 className="section-title">AI 助手</h3>
          <p className="muted" style={{ fontSize: 13, lineHeight: 1.8 }}>
            「创建一个 120×80×35 的吊孔盒并加上烫金」<br />
            自然语言直接生成盒型、工艺与计算。
          </p>
          <div className="mt"><Link className="btn btn-primary" to="/ai"><Sparkles size={14} /> 打开 AI 助手</Link></div>
        </div>
      </div>
    </div>
  )
}
