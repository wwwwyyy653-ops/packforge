import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import DielineView from '../components/DielineView'
import Preview3D from '../components/Preview3D'
import type { DielineData } from '../fold3d'

const DEFAULT_PARAMS: Record<string, any> = {
  length: 120, width: 80, height: 35, thickness: 0.45, glueWidth: 15,
}

export default function Designer() {
  const [sp, setSp] = useSearchParams()
  const [projects, setProjects] = useState<any[]>([])
  const [projectId, setProjectId] = useState('')
  const [boxTypes, setBoxTypes] = useState<any[]>([])
  const [boxType, setBoxType] = useState(sp.get('boxType') || 'tuck-end')
  const [boxes, setBoxes] = useState<any[]>([])
  const [currentBox, setCurrentBox] = useState<any>(null)
  const [params, setParams] = useState<Record<string, any>>({ ...DEFAULT_PARAMS })
  const [material, setMaterial] = useState('350g 白卡')
  const [notes, setNotes] = useState('')
  const [tags, setTags] = useState('')
  const [tab, setTab] = useState<'2d' | '3d' | 'preflight' | 'info' | 'cost' | 'history'>('2d')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [costInputs, setCostInputs] = useState({ quantity: 5000, grammage: 350, paperPricePerKg: 6.5, colors: 4, printType: 'offset', finishes: [] as string[], profitRate: 0.25 })
  const [finishes, setFinishes] = useState<any[]>([])
  const [costResult, setCostResult] = useState<any>(null)
  const [versions, setVersions] = useState<any[]>([])

  useEffect(() => {
    api.projects().then(list => {
      setProjects(list)
      const fromUrl = sp.get('project')
      if (fromUrl && list.some(p => p.id === fromUrl)) {
        setProjectId(fromUrl)
      } else if (list.length) {
        setProjectId(list[0].id)
      }
    }).catch(() => {})
    api.boxTypes().then(r => setBoxTypes(r.boxTypes)).catch(() => {})
    api.finishes().then((r: any) => setFinishes(r.finishes || [])).catch(() => {})
  }, [])

  const loadBoxes = useCallback((pid: string) => {
    if (!pid) return
    api.boxes(pid).then(list => {
      setBoxes(list)
      if (list.length) {
        const last = list[list.length - 1]
        setCurrentBox(last)
        setParams({ ...DEFAULT_PARAMS, ...last.parameters })
        setBoxType(last.boxType)
        setMaterial(last.material || '350g 白卡')
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (projectId) loadBoxes(projectId)
  }, [projectId, loadBoxes])

  const typeInfo = useMemo(() => boxTypes.find(t => t.id === boxType), [boxTypes, boxType])

  const changeType = (id: string) => {
    setBoxType(id)
    setParams({ ...DEFAULT_PARAMS })
  }

  const setParam = (k: string, v: any) => setParams(p => ({ ...p, [k]: v }))

  const createBox = async () => {
    if (!projectId) { setMsg('请先选择或创建项目'); return }
    setBusy(true); setMsg('')
    try {
      const box = await api.createBox({
        projectId, boxType,
        parameters: { ...params },
        material, notes, tags,
      })
      setCurrentBox(box)
      loadBoxes(projectId)
      setMsg(`已创建：${box.label}（${box.dieline.flatWidth}×${box.dieline.flatHeight}mm）`)
    } catch (e: any) {
      setMsg('创建失败：' + e.message)
    } finally { setBusy(false) }
  }

  const updateBox = async () => {
    if (!currentBox) { setMsg('请先选择盒型'); return }
    setBusy(true); setMsg('')
    try {
      const box = await api.updateBox(currentBox.id, { parameters: { ...params }, boxType, notes, tags, material })
      setCurrentBox(box)
      loadBoxes(projectId)
      api.boxVersions(box.id).then(setVersions).catch(() => {})
      setMsg(`参数已更新，几何已重算（v${box.version}）`)
    } catch (e: any) {
      setMsg('更新失败：' + e.message)
    } finally { setBusy(false) }
  }

  const selectBox = (b: any) => {
    setCurrentBox(b)
    setParams({ ...DEFAULT_PARAMS, ...b.parameters })
    setBoxType(b.boxType)
    setMaterial(b.material || '350g 白卡')
    setNotes(b.notes || '')
    setTags(b.tags || '')
    setCostResult(null)
    api.boxVersions(b.id).then(setVersions).catch(() => setVersions([]))
  }

  const deleteBox = async () => {
    if (!currentBox) return
    if (!confirm(`确定删除盒型「${currentBox.label}」？`)) return
    try {
      await api.deleteBox(currentBox.id)
      setCurrentBox(null)
      loadBoxes(projectId)
      setMsg('盒型已删除')
    } catch (e: any) {
      setMsg('删除失败：' + e.message)
    }
  }

  const saveAsRecipe = async () => {
    const name = window.prompt('配方名称：', `${boxType} 方案`)
    if (!name || !name.trim()) return
    try {
      await api.createRecipe({
        name: name.trim(), boxType, parameters: { ...params },
        material, finishes: costInputs.finishes,
        prompt: `创建 ${params.length}×${params.width}×${params.height} 的${boxType}`,
      })
      setMsg(`配方「${name.trim()}」已保存，可在 AI 助手页一键复用`)
    } catch (e: any) {
      setMsg('保存配方失败：' + e.message)
    }
  }

  const calcCost = async () => {
    if (!currentBox) return
    setBusy(true)
    try {
      const r = await api.boxCost(currentBox.id, costInputs)
      setCostResult(r)
    } catch (e: any) {
      setMsg('成本估算失败：' + e.message)
    } finally { setBusy(false) }
  }

  const dl: DielineData | null = useMemo(() => currentBox?.dieline ?? null, [currentBox])

  return (
    <div style={{ height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h1 className="page-title">盒型设计器</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>参数化刀模 · 2D 展开 · 3D 折叠 · 印前预检 · 生产导出</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {projectId && (
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center', marginRight: 4 }}>
              <span className="muted" style={{ fontSize: 12 }}>批量导出本项目:</span>
              <a className="btn btn-sm" href={api.bundleUrl(projectId, 'svg')} download>SVG包</a>
              <a className="btn btn-sm" href={api.bundleUrl(projectId, 'dxf')} download>DXF包</a>
              <a className="btn btn-sm" href={api.bundleUrl(projectId, 'pdf')} download>PDF包</a>
            </span>
          )}
          {dl && (<>
            <a className="btn" href={api.exportUrl(currentBox.id, 'svg')} download>导出 SVG</a>
            <a className="btn" href={api.exportUrl(currentBox.id, 'dxf')} download>导出 DXF</a>
            <a className="btn" href={api.exportUrl(currentBox.id, 'pdf')} download>导出 PDF</a>
            <button className="btn btn-danger" onClick={deleteBox}>删除盒型</button>
          </>)}
        </div>
      </div>

      <div className="designer">
        <div className="designer-left">
          <div className="card" style={{ padding: 16 }}>
            <div className="field">
              <label>项目</label>
              <select className="input" value={projectId} onChange={e => { setProjectId(e.target.value); loadBoxes(e.target.value) }}>
                {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="field">
              <label>盒型模板</label>
              <select className="input" value={boxType} onChange={e => changeType(e.target.value)}>
                {boxTypes.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </div>
            <div className="row">
              <div className="field"><label>长 L (mm)</label>
                <input type="number" className="input" value={params.length ?? ''} min={10}
                  onChange={e => setParam('length', parseFloat(e.target.value) || 0)} /></div>
              <div className="field"><label>宽 W (mm)</label>
                <input type="number" className="input" value={params.width ?? ''} min={10}
                  onChange={e => setParam('width', parseFloat(e.target.value) || 0)} /></div>
              <div className="field"><label>高 H (mm)</label>
                <input type="number" className="input" value={params.height ?? ''} min={5}
                  onChange={e => setParam('height', parseFloat(e.target.value) || 0)} /></div>
            </div>
            <div className="row">
              <div className="field"><label>纸厚 (mm)</label>
                <input type="number" step={0.05} className="input" value={params.thickness ?? ''}
                  onChange={e => setParam('thickness', parseFloat(e.target.value) || 0)} /></div>
              <div className="field"><label>糊口 (mm)</label>
                <input type="number" className="input" value={params.glueWidth ?? ''}
                  onChange={e => setParam('glueWidth', parseFloat(e.target.value) || 0)} /></div>
            </div>
            {typeInfo?.specials?.map(([key, label]: [string, string]) => (
              <div className="field" key={key}>
                <label>{label}</label>
                <input type="number" className="input" value={params[key] ?? ''}
                  onChange={e => setParam(key, parseFloat(e.target.value) || 0)} />
              </div>
            ))}
            <div className="field">
              <label>备注</label>
              <textarea className="input" rows={2} value={notes}
                onChange={e => setNotes(e.target.value)} placeholder="用途、客户、工艺要求…" />
            </div>
            <div className="field">
              <label>标签（逗号分隔）</label>
              <input type="text" className="input" value={tags}
                onChange={e => setTags(e.target.value)} placeholder="如：食品, 节日礼盒" />
            </div>
            <div className="row" style={{ marginTop: 4 }}>
              <button className="btn btn-primary" onClick={createBox} disabled={busy}>生成刀模</button>
              <button className="btn" onClick={updateBox} disabled={busy || !currentBox}>更新参数</button>
              <button className="btn" onClick={saveAsRecipe} disabled={busy}>存为配方</button>
            </div>
            {msg && <div style={{ fontSize: 12, marginTop: 8, color: msg.startsWith('已') ? 'var(--ok)' : 'var(--danger)' }}>{msg}</div>}
          </div>

          <div className="card" style={{ padding: 16 }}>
            <div className="section-title">项目盒型列表</div>
            {boxes.length === 0 && <div className="muted" style={{ fontSize: 12 }}>暂无盒型</div>}
            {boxes.map(b => (
              <div key={b.id} onClick={() => selectBox(b)}
                style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 10px', cursor: 'pointer', borderRadius: 8, fontSize: 13,
                  background: currentBox?.id === b.id ? 'rgba(99,102,241,.18)' : 'transparent',
                  borderLeft: currentBox?.id === b.id ? '3px solid var(--primary)' : '3px solid transparent' }}>
                <span>{b.label}</span>
                <span className="muted">{b.dieline.flatWidth}×{b.dieline.flatHeight}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="designer-right">
          <div className="preview-tabs">
            <button className={`tab-btn ${tab === '2d' ? 'active' : ''}`} onClick={() => setTab('2d')}>2D 刀模</button>
            <button className={`tab-btn ${tab === '3d' ? 'active' : ''}`} onClick={() => setTab('3d')}>3D 折叠</button>
            <button className={`tab-btn ${tab === 'preflight' ? 'active' : ''}`} onClick={() => setTab('preflight')}>印前预检</button>
            <button className={`tab-btn ${tab === 'info' ? 'active' : ''}`} onClick={() => setTab('info')}>几何信息</button>
            <button className={`tab-btn ${tab === 'cost' ? 'active' : ''}`} onClick={() => setTab('cost')}>成本估算</button>
            <button className={`tab-btn ${tab === 'history' ? 'active' : ''}`} onClick={() => setTab('history')}>版本历史</button>
          </div>

          {!dl && <div className="card empty">请先选择项目并生成盒型</div>}

          {dl && tab === '2d' && <DielineView dl={dl} />}
          {dl && tab === '3d' && <div style={{ flex: 1 }}><Preview3D dl={dl} /></div>}
          {dl && tab === 'preflight' && <PreflightPanel report={currentBox.preflight} />}
          {dl && tab === 'info' && <InfoPanel box={currentBox} />}
          {dl && tab === 'cost' && <CostPanel box={currentBox} inputs={costInputs} setInputs={setCostInputs} onCalc={calcCost} result={costResult} busy={busy} finishes={finishes} />}
          {dl && tab === 'history' && <HistoryPanel versions={versions} currentBox={currentBox} />}
        </div>
      </div>
    </div>
  )
}

function PreflightPanel({ report }: { report: any }) {
  if (!report) return <div className="card empty">无预检数据</div>
  const issues: any[] = report.issues || []
  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <span className={`badge ${report.passed ? 'badge-ok' : 'badge-error'}`} style={{ fontSize: 13 }}>
          {report.passed ? '✅ 通过' : '❌ 存在问题'}
        </span>
        <span className="muted" style={{ fontSize: 12 }}>
          面板 {report.stats.panels} · 折痕 {report.stats.folds} · 孔洞 {report.stats.holes} · 展开 {report.stats.flat_width_mm}×{report.stats.flat_height_mm}mm
        </span>
      </div>
      <div className="preflight-list">
        {issues.length === 0 && <div className="muted">未发现几何 / 制造问题</div>}
        {issues.map((it, i) => (
          <div key={i} className={`preflight-item ${it.severity}`}>
            <span>{it.severity === 'error' ? '⛔' : it.severity === 'warning' ? '⚠️' : 'ℹ️'}</span>
            <span>{it.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function InfoPanel({ box }: { box: any }) {
  const dl = box.dieline
  let panelCount = 0, foldCount = 0, holeCount = 0
  dl?.pieces?.forEach((pc: any) => {
    panelCount += Object.keys(pc.panels).length
    foldCount += pc.folds.length
    for (const spec of Object.values(pc.panels) as any[]) holeCount += (spec.holes || []).length
  })
  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="kv">
        <div className="kv-item"><div className="k">盒型</div><div className="v">{box.label}</div></div>
        <div className="kv-item"><div className="k">展开尺寸</div><div className="v">{dl.flatWidth} × {dl.flatHeight} mm</div></div>
        <div className="kv-item"><div className="k">面板数</div><div className="v">{panelCount}</div></div>
        <div className="kv-item"><div className="k">折痕数</div><div className="v">{foldCount}</div></div>
        <div className="kv-item"><div className="k">孔洞数</div><div className="v">{holeCount}</div></div>
        <div className="kv-item"><div className="k">材质</div><div className="v">{box.material}</div></div>
      </div>
      <div className="mt">
        <div className="section-title">参数</div>
        <table>
          <tbody>
            {Object.entries(box.parameters || {}).map(([k, v]) => (
              <tr key={k}><td style={{ color: 'var(--muted)' }}>{k}</td><td>{String(v)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {box.notes && (
        <div className="mt">
          <div className="section-title">备注</div>
          <div className="muted" style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{box.notes}</div>
        </div>
      )}
    </div>
  )
}

function CostPanel({ box, inputs, setInputs, onCalc, result, busy, finishes }: any) {
  const e = result?.estimate
  const toggleFinish = (fid: string) => {
    const has = inputs.finishes.includes(fid)
    setInputs({ ...inputs, finishes: has ? inputs.finishes.filter((x: string) => x !== fid) : [...inputs.finishes, fid] })
  }
  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="section-title">成本估算（基于刀模展开面积 {result ? result.areaM2 : '—'} m²）</div>
      <div className="row">
        <div className="field"><label>数量（个）</label>
          <input type="number" className="input" value={inputs.quantity} onChange={(ev: any) => setInputs({ ...inputs, quantity: +ev.target.value })} /></div>
        <div className="field"><label>克重（g/m²）</label>
          <input type="number" className="input" value={inputs.grammage} onChange={(ev: any) => setInputs({ ...inputs, grammage: +ev.target.value })} /></div>
      </div>
      <div className="row">
        <div className="field"><label>纸价（元/kg）</label>
          <input type="number" step={0.1} className="input" value={inputs.paperPricePerKg} onChange={(ev: any) => setInputs({ ...inputs, paperPricePerKg: +ev.target.value })} /></div>
        <div className="field"><label>印刷色数</label>
          <input type="number" className="input" value={inputs.colors} onChange={(ev: any) => setInputs({ ...inputs, colors: +ev.target.value })} /></div>
        <div className="field"><label>印刷方式</label>
          <select className="input" value={inputs.printType} onChange={(ev: any) => setInputs({ ...inputs, printType: ev.target.value })}>
            <option value="offset">胶印</option>
            <option value="digital">数码</option>
            <option value="flexo">柔印</option>
          </select></div>
        <div className="field"><label>利润率</label>
          <input type="number" step={0.05} className="input" value={inputs.profitRate} onChange={(ev: any) => setInputs({ ...inputs, profitRate: +ev.target.value })} /></div>
      </div>
      <div className="field">
        <label>后道工艺（多选）</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {finishes.map((f: any) => (
            <label key={f.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 13,
              padding: '5px 10px', borderRadius: 8, cursor: 'pointer',
              background: inputs.finishes.includes(f.id) ? 'rgba(34,211,238,.15)' : 'rgba(255,255,255,.04)',
              border: `1px solid ${inputs.finishes.includes(f.id) ? 'var(--accent)' : 'var(--line)'}` }}>
              <input type="checkbox" checked={inputs.finishes.includes(f.id)} onChange={() => toggleFinish(f.id)} style={{ accentColor: 'var(--accent)' }} />
              {f.name} <span className="muted">¥{f.price_per_m2}/m²</span>
            </label>
          ))}
        </div>
      </div>
      <button className="btn btn-primary" onClick={onCalc} disabled={busy}>{busy ? '计算中…' : '估算成本'}</button>
      {e && (
        <div className="tool-result">
          <h4>估算结果</h4>
          <div className="kv">
            <div className="kv-item"><div className="k">材料成本</div><div className="v">¥{e.material_cost?.toFixed(2)}</div></div>
            <div className="kv-item"><div className="k">印刷成本</div><div className="v">¥{e.print_cost?.toFixed(2)}</div></div>
            <div className="kv-item"><div className="k">后道工艺</div><div className="v">¥{e.finish_cost?.toFixed(2)}</div></div>
            <div className="kv-item"><div className="k">模切/人工</div><div className="v">¥{(e.diecut_cost + e.glue_cost + e.labor_cost)?.toFixed(2)}</div></div>
            <div className="kv-item"><div className="k">损耗(5%)</div><div className="v">¥{e.waste_cost?.toFixed(2)}</div></div>
            <div className="kv-item"><div className="k">总成本</div><div className="v" style={{ color: 'var(--primary-2)' }}>¥{e.total_cost?.toFixed(2)}</div></div>
            <div className="kv-item"><div className="k">单件成本</div><div className="v" style={{ color: 'var(--accent)' }}>¥{e.unit_cost?.toFixed(4)}</div></div>
            <div className="kv-item"><div className="k">建议售价</div><div className="v" style={{ color: 'var(--ok)' }}>¥{e.suggested_price?.toFixed(4)}</div></div>
          </div>
        </div>
      )}
    </div>
  )
}

function HistoryPanel({ versions, currentBox }: any) {
  const [sel, setSel] = useState<any>(null)
  const cur = currentBox?.parameters || {}
  const old = sel?.parameters || {}
  const keys = Array.from(new Set([...Object.keys(old), ...Object.keys(cur)]))
  const diffCount = keys.filter(k => String(old[k]) !== String(cur[k])).length
  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="section-title">版本历史（当前 v{currentBox?.version}）</div>
      {versions.length === 0 && <div className="muted" style={{ fontSize: 13 }}>暂无历史版本。每次"更新参数"都会自动快照旧版本。</div>}
      {versions.length > 0 && (
        <table>
          <thead><tr><th>版本</th><th>标签</th><th>材质</th><th>备注</th><th>保存时间</th><th></th></tr></thead>
          <tbody>
            {versions.map((v: any) => (
              <tr key={v.id} style={{ cursor: 'pointer', background: sel?.id === v.id ? 'rgba(99,102,241,.12)' : undefined }}
                onClick={() => setSel(sel?.id === v.id ? null : v)}>
                <td><span className="badge badge-draft">v{v.version}</span></td>
                <td>{v.label}</td>
                <td>{v.material}</td>
                <td className="muted">{v.notes || '—'}</td>
                <td className="muted">{new Date(v.createdAt * 1000).toLocaleString('zh-CN')}</td>
                <td><span className="muted" style={{ fontSize: 12 }}>{sel?.id === v.id ? '收起' : '对比'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {sel && (
        <div className="mt">
          <div className="section-title">v{sel.version} → v{currentBox?.version} 参数差异（{diffCount} 项变化）</div>
          <table>
            <thead><tr><th>参数</th><th>旧 v{sel.version}</th><th>当前 v{currentBox?.version}</th></tr></thead>
            <tbody>
              {keys.map(k => {
                const changed = String(old[k]) !== String(cur[k])
                return (
                  <tr key={k} style={changed ? { background: 'rgba(251,191,36,.08)' } : undefined}>
                    <td style={{ color: 'var(--muted)' }}>{k}</td>
                    <td style={changed ? { color: '#fcd34d' } : undefined}>{old[k] ?? '—'}</td>
                    <td style={changed ? { color: 'var(--ok)', fontWeight: 600 } : undefined}>{cur[k] ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
