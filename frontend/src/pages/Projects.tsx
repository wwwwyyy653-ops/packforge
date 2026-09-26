import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Projects() {
  const nav = useNavigate()
  const [projects, setProjects] = useState<any[]>([])
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [creating, setCreating] = useState(false)

  const load = () => api.projects().then(setProjects).catch(() => {})
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!name.trim()) return
    setCreating(true)
    try {
      const p = await api.createProject({ name: name.trim(), description: desc, status: 'draft' })
      setName(''); setDesc('')
      nav(`/designer?project=${p.id}`)
    } finally { setCreating(false) }
  }

  const del = async (id: string, ev: React.MouseEvent) => {
    ev.stopPropagation()
    if (!confirm('确定删除该项目及其所有盒型？')) return
    await api.deleteProject(id)
    load()
  }

  return (
    <div>
      <h1 className="page-title">项目管理</h1>
      <p className="page-sub">创建、组织和管理包装设计项目</p>

      <div className="card" style={{ padding: 20, marginBottom: 20 }}>
        <div className="row">
          <div className="field" style={{ flex: 2, marginBottom: 0 }}>
            <label>项目名称</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)}
              placeholder="例如：食品礼盒包装设计" onKeyDown={e => e.key === 'Enter' && create()} />
          </div>
          <div className="field" style={{ flex: 3, marginBottom: 0 }}>
            <label>描述</label>
            <input className="input" value={desc} onChange={e => setDesc(e.target.value)} placeholder="可选" />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button className="btn btn-primary" onClick={create} disabled={creating || !name.trim()}>
              新建项目
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-2">
        {projects.map(p => (
          <div key={p.id} className="card card-hover" style={{ padding: 18 }}
            onClick={() => nav(`/designer?project=${p.id}`)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{p.name}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{p.description || '—'}</div>
              </div>
              <span className={`badge badge-${p.status}`}>{p.status}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
              <span className="muted" style={{ fontSize: 12 }}>
                {p.boxCount ?? 0} 个盒型 · 更新于 {new Date(p.updatedAt * 1000).toLocaleDateString()}
              </span>
              <span style={{ display: 'inline-flex', gap: 6 }} onClick={e => e.stopPropagation()}>
                <a className="btn btn-sm" href={api.bundleUrl(p.id, 'svg')} download title="打包全部 SVG">SVG 包</a>
                <a className="btn btn-sm" href={api.bundleUrl(p.id, 'dxf')} download title="打包全部 DXF">DXF 包</a>
                <button className="btn btn-sm btn-danger" onClick={e => del(p.id, e)}>删除</button>
              </span>
            </div>
          </div>
        ))}
        {projects.length === 0 && <div className="empty">还没有项目，先创建一个吧</div>}
      </div>
    </div>
  )
}
