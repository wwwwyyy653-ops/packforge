import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { LayoutDashboard, FolderKanban, Shapes, Wrench, Sparkles, Package } from 'lucide-react'
import { api } from './api'
import Home from './pages/Home'
import Projects from './pages/Projects'
import Designer from './pages/Designer'
import Tools from './pages/Tools'
import AI from './pages/AI'

const NAV = [
  { to: '/', end: true, label: '工作台', icon: LayoutDashboard },
  { to: '/projects', label: '项目管理', icon: FolderKanban },
  { to: '/designer', label: '盒型设计器', icon: Shapes },
  { to: '/tools', label: '包装工具箱', icon: Wrench },
  { to: '/ai', label: 'AI 助手', icon: Sparkles },
]

export default function App() {
  const [health, setHealth] = useState<string>('连接中…')

  useEffect(() => {
    api.health().then(h => setHealth(`后端就绪 · ${h.boxTypes} 种盒型`))
      .catch(() => setHealth('后端未连接（请先运行 backend\\run.py）'))
  }, [])

  return (
    <div className="app">
      <div className="bg-glow" />
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo"><Package size={20} strokeWidth={2.2} /></div>
          <div>
            <div className="brand-name">包装参数化设计</div>
            <div className="brand-sub">PACKAGING STUDIO</div>
          </div>
        </div>
        <nav>
          {NAV.map(n => (
            <NavLink key={n.to} to={n.to} end={n.end ?? false}
              className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
              <n.icon size={16} className="nav-icon" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={`dot ${health.includes('就绪') ? 'ok' : health.includes('未连接') ? 'bad' : ''}`} />
          {health}
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/designer" element={<Designer />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/ai" element={<AI />} />
        </Routes>
      </main>
    </div>
  )
}
