import { useEffect, useState } from 'react'
import { api } from '../api'

type ToolId = 'bct' | 'imposition' | 'paper' | 'container' | 'cost'

const TOOLS: { id: ToolId; label: string; icon: string; desc: string }[] = [
  { id: 'bct', label: '抗压计算', icon: '💪', desc: 'McKee 公式 BCT 抗压强度与堆码' },
  { id: 'imposition', label: '拼版算料', icon: '📐', desc: '纸张利用率与排布优化' },
  { id: 'paper', label: '纸张换算', icon: '📄', desc: '克重 ↔ 厚度换算' },
  { id: 'container', label: '装柜模拟', icon: '🚢', desc: '20GP/40GP/40HQ 装柜排布' },
  { id: 'cost', label: '成本估算', icon: '💰', desc: '印刷成本与建议报价' },
]

export default function Tools() {
  const [tab, setTab] = useState<ToolId>('bct')
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [mats, setMats] = useState<any[]>([])
  const [paperTypes, setPaperTypes] = useState<any[]>([])
  const [containers, setContainers] = useState<any>({})

  useEffect(() => {
    api.materials().then(r => setMats(r.materials)).catch(() => {})
    api.paperTypes().then(r => setPaperTypes(r.types)).catch(() => {})
    api.containers().then(r => setContainers(r.containers)).catch(() => {})
  }, [])

  const [bct, setBct] = useState({ ect: 5000, thickness: 3, length: 300, width: 200, stackHeight: 2000, safetyFactor: 1.6, humidityDecay: 0 })
  const [imp, setImp] = useState({ boxWidth: 100, boxHeight: 80, sheetWidth: 500, sheetHeight: 700, trim: 5, glue: 0 })
  const [paper, setPaper] = useState({ value: 350, paperType: 'white-card', direction: 'g2t' })
  const [cont, setCont] = useState({ containerId: '40HQ', boxLength: 400, boxWidth: 300, boxHeight: 200, boxWeightKg: 1.5 })
  const [cost, setCost] = useState({ quantity: 2000, areaM2: 0.1, grammage: 350, paperPricePerKg: 8.5, colors: 4, printType: 'offset', finishes: [] as string[], profitRate: 0.25 })

  const run = async () => {
    setBusy(true); setResult(null)
    try {
      let r: any
      if (tab === 'bct') r = await api.bct(bct)
      if (tab === 'imposition') r = await api.imposition(imp)
      if (tab === 'paper') r = await api.paper(paper)
      if (tab === 'container') r = await api.container(cont)
      if (tab === 'cost') r = await api.cost(cost)
      setResult(r)
    } catch (e: any) { setResult({ error: e.message }) }
    finally { setBusy(false) }
  }

  const setF = (setter: any) => (k: string) => (e: any) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setter((s: any) => ({ ...s, [k]: v }))
  }
  const num = (setter: any) => (k: string) => (e: any) =>
    setter((s: any) => ({ ...s, [k]: parseFloat(e.target.value) || 0 }))

  return (
    <div>
      <h1 className="page-title">包装工具箱</h1>
      <p className="page-sub">免费包装行业计算工具：抗压 / 拼版 / 纸张 / 装柜 / 成本</p>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        {TOOLS.map(t => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`} onClick={() => { setTab(t.id); setResult(null) }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="tools-wrap">
        <div className="card" style={{ padding: 20 }}>
          {tab === 'bct' && (
            <div>
              <h3 className="section-title">McKee 抗压强度计算</h3>
              <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>BCT = 5.87 × ECT × √(d × Z)，适用于瓦楞纸箱</p>
              <div className="grid grid-3">
                <div className="field"><label>边压强度 ECT (N/m)</label>
                  <input type="number" className="input" value={bct.ect} onChange={num(setBct)('ect')} /></div>
                <div className="field"><label>纸板厚度 (mm)</label>
                  <input type="number" step={0.1} className="input" value={bct.thickness} onChange={num(setBct)('thickness')} /></div>
                <div className="field"><label>箱长 (mm)</label>
                  <input type="number" className="input" value={bct.length} onChange={num(setBct)('length')} /></div>
                <div className="field"><label>箱宽 (mm)</label>
                  <input type="number" className="input" value={bct.width} onChange={num(setBct)('width')} /></div>
                <div className="field"><label>堆码高度 (mm)</label>
                  <input type="number" className="input" value={bct.stackHeight} onChange={num(setBct)('stackHeight')} /></div>
                <div className="field"><label>安全系数</label>
                  <input type="number" step={0.1} className="input" value={bct.safetyFactor} onChange={num(setBct)('safetyFactor')} /></div>
              </div>
            </div>
          )}

          {tab === 'imposition' && (
            <div>
              <h3 className="section-title">拼版算料利用率</h3>
              <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>自动穷举正放 / 旋转90° / 混合交错三种排布</p>
              <div className="grid grid-3">
                <div className="field"><label>展开宽 (mm)</label>
                  <input type="number" className="input" value={imp.boxWidth} onChange={num(setImp)('boxWidth')} /></div>
                <div className="field"><label>展开高 (mm)</label>
                  <input type="number" className="input" value={imp.boxHeight} onChange={num(setImp)('boxHeight')} /></div>
                <div className="field"><label>纸张宽 (mm)</label>
                  <input type="number" className="input" value={imp.sheetWidth} onChange={num(setImp)('sheetWidth')} /></div>
                <div className="field"><label>纸张高 (mm)</label>
                  <input type="number" className="input" value={imp.sheetHeight} onChange={num(setImp)('sheetHeight')} /></div>
                <div className="field"><label>修边 (mm)</label>
                  <input type="number" className="input" value={imp.trim} onChange={num(setImp)('trim')} /></div>
                <div className="field"><label>糊口附加 (mm)</label>
                  <input type="number" className="input" value={imp.glue} onChange={num(setImp)('glue')} /></div>
              </div>
            </div>
          )}

          {tab === 'paper' && (
            <div>
              <h3 className="section-title">纸张克重 ↔ 厚度换算</h3>
              <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>基于纸种密度换算（GB/T 451.3 思路）</p>
              <div className="row" style={{ maxWidth: 640 }}>
                <div className="field"><label>方向</label>
                  <select className="input" value={paper.direction} onChange={setF(setPaper)('direction')}>
                    <option value="g2t">克重 → 厚度</option>
                    <option value="t2g">厚度 → 克重</option>
                  </select></div>
                <div className="field"><label>{paper.direction === 'g2t' ? '克重 (g/m²)' : '厚度 (mm)'}</label>
                  <input type="number" className="input" value={paper.value} onChange={num(setPaper)('value')} /></div>
                <div className="field"><label>纸种</label>
                  <select className="input" value={paper.paperType} onChange={setF(setPaper)('paperType')}>
                    {paperTypes.map((t: any) => <option key={t.id} value={t.id}>{t.label}</option>)}
                  </select></div>
              </div>
            </div>
          )}

          {tab === 'container' && (
            <div>
              <h3 className="section-title">集装箱装柜模拟</h3>
              <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>6 种朝向穷举，输出最优装柜方案</p>
              <div className="grid grid-3">
                <div className="field"><label>柜型</label>
                  <select className="input" value={cont.containerId} onChange={setF(setCont)('containerId')}>
                    {Object.entries(containers).map(([k, v]: any) => <option key={k} value={k}>{k} · {v.name}</option>)}
                  </select></div>
                <div className="field"><label>箱长 (mm)</label>
                  <input type="number" className="input" value={cont.boxLength} onChange={num(setCont)('boxLength')} /></div>
                <div className="field"><label>箱宽 (mm)</label>
                  <input type="number" className="input" value={cont.boxWidth} onChange={num(setCont)('boxWidth')} /></div>
                <div className="field"><label>箱高 (mm)</label>
                  <input type="number" className="input" value={cont.boxHeight} onChange={num(setCont)('boxHeight')} /></div>
                <div className="field"><label>单箱重量 (kg)</label>
                  <input type="number" step={0.1} className="input" value={cont.boxWeightKg} onChange={num(setCont)('boxWeightKg')} /></div>
              </div>
            </div>
          )}

          {tab === 'cost' && (
            <div>
              <h3 className="section-title">印刷成本估算</h3>
              <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>材料 / 印刷 / 后道 / 模切 / 糊盒 / 人工 / 损耗</p>
              <div className="grid grid-3">
                <div className="field"><label>数量</label>
                  <input type="number" className="input" value={cost.quantity} onChange={num(setCost)('quantity')} /></div>
                <div className="field"><label>单件面积 (m²)</label>
                  <input type="number" step={0.01} className="input" value={cost.areaM2} onChange={num(setCost)('areaM2')} /></div>
                <div className="field"><label>克重 (g/m²)</label>
                  <input type="number" className="input" value={cost.grammage} onChange={num(setCost)('grammage')} /></div>
                <div className="field"><label>纸价 (元/kg)</label>
                  <input type="number" step={0.1} className="input" value={cost.paperPricePerKg} onChange={num(setCost)('paperPricePerKg')} /></div>
                <div className="field"><label>色数</label>
                  <input type="number" className="input" value={cost.colors} onChange={num(setCost)('colors')} /></div>
                <div className="field"><label>印刷方式</label>
                  <select className="input" value={cost.printType} onChange={setF(setCost)('printType')}>
                    <option value="offset">胶印</option><option value="digital">数码</option><option value="flexo">柔印</option>
                  </select></div>
              </div>
              <div className="field">
                <label>后道工艺</label>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {['matte', 'gloss', 'uv', 'spot-uv', 'foil', 'emboss', 'laminate'].map(f => (
                    <label key={f} style={{ fontSize: 12, display: 'flex', gap: 4, alignItems: 'center' }}>
                      <input type="checkbox" checked={cost.finishes.includes(f)}
                        onChange={e => setCost(s => ({ ...s, finishes: e.target.checked ? [...s.finishes, f] : s.finishes.filter(x => x !== f) }))} />
                      {({ matte: '哑膜', gloss: '光膜', uv: 'UV', 'spot-uv': '局部UV', foil: '烫金', emboss: '击凸', laminate: '覆膜' } as any)[f]}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="mt">
            <button className="btn btn-primary" onClick={run} disabled={busy}>{busy ? '计算中…' : '开始计算'}</button>
          </div>

          {result && !result.error && <ToolResult tab={tab} result={result} />}
          {result?.error && <div className="tool-result" style={{ color: 'var(--danger)' }}>错误：{result.error}</div>}
        </div>

        <div className="card" style={{ padding: 20 }}>
          <h3 className="section-title">常用材质库</h3>
          <table>
            <thead><tr><th>材质</th><th>厚度</th><th>克重</th><th>中性层系数</th></tr></thead>
            <tbody>
              {mats.map(m => (
                <tr key={m.id}>
                  <td>{m.name}</td><td>{m.thickness}mm</td>
                  <td>{m.grammage ?? '—'}</td><td>{m.neutral}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function ToolResult({ tab, result }: { tab: ToolId; result: any }) {
  const r = result.result
  if (tab === 'bct') return (
    <div className="tool-result">
      <h4>抗压结果</h4>
      <div className="kv">
        <div className="kv-item"><div className="k">BCT 抗压强度</div><div className="v">{r.bct_n} N</div></div>
        <div className="kv-item"><div className="k">≈ 承载</div><div className="v">{r.bct_kg} kg</div></div>
        <div className="kv-item"><div className="k">安全堆码层数</div><div className="v">{r.safe_stack_count}</div></div>
        <div className="kv-item"><div className="k">实际安全系数</div><div className="v">{r.actual_safety_factor}</div></div>
        <div className="kv-item"><div className="k">风险等级</div>
          <div className="v"><span className={`badge badge-${r.risk_level === 'safe' ? 'ok' : r.risk_level === 'warning' ? 'warn' : 'error'}`}>{r.risk_level}</span></div></div>
      </div>
      <p style={{ marginTop: 10, fontSize: 13 }}>{r.recommendation}</p>
    </div>
  )
  if (tab === 'imposition') return (
    <div className="tool-result">
      <h4>拼版结果（最优：{r.best.name}）</h4>
      <div className="kv">
        <div className="kv-item"><div className="k">排布数</div><div className="v">{r.maxCount} 个</div></div>
        <div className="kv-item"><div className="k">利用率</div><div className="v">{r.utilization}%</div></div>
        <div className="kv-item"><div className="k">废料面积</div><div className="v">{r.wasteArea} mm²</div></div>
      </div>
      <table className="mt"><thead><tr><th>方案</th><th>旋转</th><th>数量</th><th>行×列</th><th>利用率</th></tr></thead>
        <tbody>
          {[r.best, ...r.alternatives].map((l: any, i: number) => (
            <tr key={i}><td>{l.name}</td><td>{l.rotation}°</td><td>{l.count}</td><td>{l.rows}×{l.columns}</td><td>{l.utilization}%</td></tr>
          ))}
        </tbody></table>
    </div>
  )
  if (tab === 'paper') return (
    <div className="tool-result">
      <h4>换算结果</h4>
      <div className="kv">
        <div className="kv-item"><div className="k">克重</div><div className="v">{r.grammage} g/m²</div></div>
        <div className="kv-item"><div className="k">厚度</div><div className="v">{r.thickness_mm} mm</div></div>
        <div className="kv-item"><div className="k">厚度 (μm)</div><div className="v">{r.thickness_um} μm</div></div>
        <div className="kv-item"><div className="k">厚度 (pt)</div><div className="v">{r.thickness_pt} pt</div></div>
        <div className="kv-item"><div className="k">松厚度</div><div className="v">{r.bulk}</div></div>
      </div>
    </div>
  )
  if (tab === 'container') return (
    <div className="tool-result">
      <h4>最优装柜：{r.best.orientation} 朝向</h4>
      <div className="kv">
        <div className="kv-item"><div className="k">总装柜数</div><div className="v">{r.total_boxes} 箱</div></div>
        <div className="kv-item"><div className="k">体积利用率</div><div className="v">{r.best.utilization}%</div></div>
        <div className="kv-item"><div className="k">列×行×层</div><div className="v">{r.best.columns}×{r.best.rows}×{r.best.layers}</div></div>
        <div className="kv-item"><div className="k">总重量</div><div className="v">{r.total_weight_kg} kg / {r.max_payload_kg} kg</div></div>
        <div className="kv-item"><div className="k">重量合规</div>
          <div className="v"><span className={`badge ${r.weight_ok ? 'badge-ok' : 'badge-error'}`}>{r.weight_ok ? '✅ 合规' : '超重'}</span></div></div>
      </div>
      <table className="mt"><thead><tr><th>朝向</th><th>数量</th><th>利用率</th></tr></thead>
        <tbody>{r.alternatives.map((a: any, i: number) => (
          <tr key={i}><td>{a.orientation}</td><td>{a.count}</td><td>{a.utilization}%</td></tr>
        ))}</tbody></table>
    </div>
  )
  if (tab === 'cost') return (
    <div className="tool-result">
      <h4>成本明细（数量 {r.quantity}）</h4>
      <div className="kv">
        <div className="kv-item"><div className="k">材料成本</div><div className="v">¥{r.material_cost}</div></div>
        <div className="kv-item"><div className="k">印刷成本</div><div className="v">¥{r.print_cost}</div></div>
        <div className="kv-item"><div className="k">后道成本</div><div className="v">¥{r.finish_cost}</div></div>
        <div className="kv-item"><div className="k">模切成本</div><div className="v">¥{r.diecut_cost}</div></div>
        <div className="kv-item"><div className="k">糊盒+人工</div><div className="v">¥{(r.glue_cost + r.labor_cost).toFixed(2)}</div></div>
        <div className="kv-item"><div className="k">损耗</div><div className="v">¥{r.waste_cost}</div></div>
        <div className="kv-item"><div className="k">总成本</div><div className="v">¥{r.total_cost}</div></div>
        <div className="kv-item"><div className="k">单件成本</div><div className="v">¥{r.unit_cost}</div></div>
        <div className="kv-item"><div className="k">建议报价</div><div className="v">¥{r.suggested_price}</div></div>
      </div>
    </div>
  )
  return null
}
