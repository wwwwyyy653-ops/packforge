import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

interface Msg { role: 'user' | 'ai'; content: string }

const EXAMPLES = [
  '创建一个 120×80×35 的吊孔盒',
  '创建一个 200×120×50 的飞机盒，用 B 瓦楞',
  '创建天地盖：长90 宽60 高40，盖深32',
  '做一个 300×200×100 的邮寄盒，算一下抗压强度',
]

export default function AI() {
  const [input, setInput] = useState('')
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: 'ai', content: '你好，我是 AI 设计助手。\n你可以用自然语言描述盒型需求，我会解析为工具调用计划并执行。\n例如：创建一个 120×80×35 的吊孔盒并加上烫金' },
  ])
  const [busy, setBusy] = useState(false)
  const [plan, setPlan] = useState<any>(null)
  const [recipes, setRecipes] = useState<any[]>([])
  const [lastBuilt, setLastBuilt] = useState<any>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, plan])
  useEffect(() => { api.recipes().then(setRecipes).catch(() => {}) }, [])

  const applyRecipe = async (r: any) => {
    setBusy(true)
    setMsgs(m => [...m, { role: 'user', content: `应用配方「${r.name}」` }])
    try {
      const projects = await api.projects()
      let pid = projects[0]?.id
      if (!pid) {
        const pj = await api.createProject({ name: '配方建盒', description: '' })
        pid = pj.id
      }
      const box = await api.createBox({
        projectId: pid,
        boxType: r.boxType,
        label: r.name,
        parameters: r.parameters,
        material: r.material || '350g 白卡',
      })
      const dl = box.dieline
      setMsgs(m => [...m, { role: 'ai', content:
        `✅ 配方「${r.name}」已建盒：\n${box.boxType} · ${r.parameters.length}×${r.parameters.width}×${r.parameters.height}mm\n展开 ${dl.flatWidth}×${dl.flatHeight}mm，${Object.keys(dl.pieces[0]?.panels ?? {}).length} 面板\n预检${box.preflight.passed ? '通过 ✓' : '有警告'}\n工艺：${(r.finishes || []).join('、') || '无'}\n可到「设计器」打开项目继续调整。` }])
    } catch (e: any) {
      setMsgs(m => [...m, { role: 'ai', content: '应用配方失败：' + e.message }])
    } finally { setBusy(false) }
  }
  const delRecipe = async (id: string, ev: React.MouseEvent) => {
    ev.stopPropagation()
    await api.deleteRecipe(id)
    setRecipes(rs => rs.filter(r => r.id !== id))
  }

  const send = async (text?: string) => {
    const prompt = (text ?? input).trim()
    if (!prompt || busy) return
    setInput('')
    setMsgs(m => [...m, { role: 'user', content: prompt }])
    setBusy(true); setPlan(null)
    try {
      const p = await api.aiPlan(prompt)
      setPlan(p)
      const summary = `🧠 已生成执行计划（风险：${p.risk}）：\n${p.steps.map((s: any) => `${s.index + 1}. ${s.summary}${s.requiresConfirmation ? '（需确认）' : ''}`).join('\n')}`
      setMsgs(m => [...m, { role: 'ai', content: summary }])
    } catch (e: any) {
      setMsgs(m => [...m, { role: 'ai', content: '解析失败：' + e.message }])
    } finally { setBusy(false) }
  }

  const execute = async (approved: boolean) => {
    if (!plan || busy) return
    setBusy(true)
    try {
      const r = await api.aiExecute(plan, approved)
      const lines = r.results.map((s: any) => {
        if (s.status === 'error') return `❌ 步骤${s.step + 1} ${s.tool}: ${s.error}`
        if (s.status === 'skipped') return `⏭️ 步骤${s.step + 1} 已跳过（未确认）`
        if (s.tool === 'box.create') return `✅ 已创建 ${s.data.label}：展开 ${s.data.flatWidth}×${s.data.flatHeight}mm，${s.data.panels} 面板，预检${s.data.preflight.passed ? '通过' : '有警告'}`
        if (s.tool === 'finish.apply') return `✨ 已应用工艺：${s.data.finishes.join(', ')}（示例成本 ¥${s.data.cost_estimate.total_cost}）`
        if (s.tool === 'box.search') return `🔍 已匹配盒型：${s.data.family}`
        return `✅ ${s.tool} 完成`
      })
      setMsgs(m => [...m, { role: 'ai', content: '🚀 执行结果：\n' + lines.join('\n') }])
      // 配方化：捕捉本次 AI 成功创建的盒型参数，供一键存为配方
      const created = r.results.find((s: any) => s.tool === 'box.create' && s.status === 'ok')
      if (created) {
        const planArgs = plan.steps.find((s: any) => s.tool === 'box.create')?.arguments || {}
        const intent = plan.intent || {}
        setLastBuilt({
          boxType: created.data.boxType,
          parameters: planArgs.parameters || intent.dimensions || {},
          material: created.data.material || intent.material || '350g 白卡',
          finishes: intent.finishes || [],
          prompt: plan.summary || '',
        })
      } else {
        setLastBuilt(null)
      }
    } catch (e: any) {
      setMsgs(m => [...m, { role: 'ai', content: '执行失败：' + e.message }])
    } finally { setBusy(false) }
  }

  const saveLastBuiltAsRecipe = async () => {
    if (!lastBuilt) return
    const name = window.prompt('配方名称：', `${lastBuilt.boxType} 方案`)
    if (!name || !name.trim()) return
    try {
      await api.createRecipe({ ...lastBuilt, name: name.trim() })
      api.recipes().then(setRecipes).catch(() => {})
      setMsgs(m => [...m, { role: 'ai', content: `📋 已保存为配方「${name.trim()}」，可在左侧配方模板一键复用。` }])
    } catch (e: any) {
      setMsgs(m => [...m, { role: 'ai', content: '保存配方失败：' + e.message }])
    }
  }

  return (
    <div>
      <h1 className="page-title">AI 助手</h1>
      <p className="page-sub">自然语言 → 意图解析 → 工具调用 → 盒型生成 / 工艺应用 / 工程计算</p>

      <div className="ai-layout">
        <div className="chat-box">
          <div className="chat-msgs">
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-ai'}`}>{m.content}</div>
            ))}
            {busy && <div className="msg msg-ai">正在解析意图…</div>}
            <div ref={bottomRef} />
          </div>
          <div className="chat-input">
            <input className="input" placeholder="描述你的包装需求…" value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()} />
            <button className="btn btn-primary" onClick={() => send()} disabled={busy || !input.trim()}>发送</button>
          </div>
          <div style={{ padding: '8px 14px', borderTop: '1px solid var(--line)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {EXAMPLES.map((ex, i) => (
              <button key={i} className="btn btn-sm" onClick={() => send(ex)}>{ex}</button>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          <div className="card" style={{ padding: 16 }}>
            <h3 className="section-title">执行计划</h3>
            {!plan && <div className="muted" style={{ fontSize: 12 }}>发送需求后，这里显示解析出的工具调用计划</div>}
            {plan && (
              <div>
                <div style={{ fontSize: 13, marginBottom: 8 }}>
                  <span className={`badge ${plan.risk === 'low' ? 'badge-ok' : 'badge-warn'}`}>风险 {plan.risk}</span>
                  <span className="muted" style={{ marginLeft: 8 }}>{plan.summary}</span>
                </div>
                {plan.steps.map((s: any) => (
                  <div key={s.index} className="plan-step">
                    <span className="muted">{s.index + 1}</span>
                    <code style={{ fontSize: 11, background: 'rgba(99,102,241,.15)', color: '#a5b4fc', padding: '2px 8px', borderRadius: 6 }}>{s.tool}</code>
                    <span>{s.summary}</span>
                    {s.requiresConfirmation && <span className="badge badge-warn">需确认</span>}
                  </div>
                ))}
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button className="btn btn-primary btn-sm" onClick={() => execute(true)} disabled={busy}>✅ 确认执行</button>
                  <button className="btn btn-sm" onClick={() => execute(false)} disabled={busy}>跳过需确认步骤</button>
                </div>
                {lastBuilt && (
                  <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 8,
                    background: 'rgba(34,211,238,.08)', border: '1px solid rgba(34,211,238,.25)' }}>
                    <div style={{ fontSize: 12, marginBottom: 6 }}>
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>本次 AI 建盒已就绪</span>
                      <span className="muted" style={{ marginLeft: 8 }}>
                        {lastBuilt.boxType} · {lastBuilt.material}{lastBuilt.finishes.length ? ' · ' + lastBuilt.finishes.join('/') : ''}
                      </span>
                    </div>
                    <button className="btn btn-sm" onClick={saveLastBuiltAsRecipe} disabled={busy}>
                      📋 存为配方
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card" style={{ padding: 16 }}>
            <h3 className="section-title">配方模板</h3>
            {recipes.length === 0 && <div className="muted" style={{ fontSize: 12 }}>暂无配方。可把常用建盒方案存为模板一键复用。</div>}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {recipes.map(r => (
                <div key={r.id} onClick={() => applyRecipe(r)}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '9px 11px', background: 'rgba(99,102,241,.08)',
                    border: '1px solid rgba(99,102,241,.25)', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                  <div>
                    <div style={{ fontWeight: 500 }}>{r.name}</div>
                    <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                      {r.boxType} · {r.material}{r.finishes?.length ? ' · ' + r.finishes.join('/') : ''}
                    </div>
                  </div>
                  <button className="btn btn-sm btn-danger" onClick={e => delRecipe(r.id, e)}>删</button>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ padding: 16 }}>
            <h3 className="section-title">可用工具</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {['box.search 盒型匹配', 'box.create 创建盒型', 'finish.apply 工艺应用', 'imposition.calculate 拼版算料', 'bct.calculate 抗压计算', 'cost.estimate 成本估算', 'container.load 装柜模拟'].map(t => (
                <div key={t} style={{ fontSize: 12, padding: '7px 11px', background: 'rgba(255,255,255,.04)', border: '1px solid var(--line)', borderRadius: 8 }}>
                  <code style={{ color: '#a5b4fc' }}>{t.split(' ')[0]}</code> <span className="muted">{t.split(' ').slice(1).join(' ')}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
