/** API 客户端 */
const BASE = '/api'

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let msg = `请求失败 ${res.status}`
    try {
      const j = await res.json()
      msg = j.detail || msg
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<any>('/health'),
  // 项目
  projects: () => req<any[]>('/projects'),
  createProject: (body: any) => req<any>('/projects', { method: 'POST', body: JSON.stringify(body) }),
  updateProject: (id: string, body: any) => req<any>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteProject: (id: string) => req<any>(`/projects/${id}`, { method: 'DELETE' }),
  // 盒型
  boxTypes: () => req<{ boxTypes: any[] }>('/ai/box-types'),
  boxes: (projectId?: string) => req<any[]>(`/boxes${projectId ? `?project_id=${projectId}` : ''}`),
  createBox: (body: any) => req<any>('/boxes', { method: 'POST', body: JSON.stringify(body) }),
  updateBox: (id: string, body: any) => req<any>(`/boxes/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteBox: (id: string) => req<any>(`/boxes/${id}`, { method: 'DELETE' }),
  folding: (id: string, progress: number) => req<any>(`/boxes/${id}/folding`, { method: 'POST', body: JSON.stringify({ progress }) }),
  boxVersions: (id: string) => req<any[]>(`/boxes/${id}/versions`),
  boxCost: (id: string, body: any) => req<any>(`/boxes/${id}/cost`, { method: 'POST', body: JSON.stringify(body) }),
  projectStats: (projectId: string) => req<any>(`/projects/${projectId}/stats`),
  // 工具箱
  bct: (body: any) => req<any>('/tools/bct', { method: 'POST', body: JSON.stringify(body) }),
  imposition: (body: any) => req<any>('/tools/imposition', { method: 'POST', body: JSON.stringify(body) }),
  paper: (body: any) => req<any>('/tools/paper', { method: 'POST', body: JSON.stringify(body) }),
  container: (body: any) => req<any>('/tools/container', { method: 'POST', body: JSON.stringify(body) }),
  cost: (body: any) => req<any>('/tools/cost', { method: 'POST', body: JSON.stringify(body) }),
  materials: () => req<any>('/tools/materials'),
  paperTypes: () => req<any>('/tools/paper-types'),
  containers: () => req<any>('/tools/containers'),
  // AI
  aiTools: () => req<any>('/ai/tools'),
  aiPlan: (prompt: string) => req<any>('/ai/plan', { method: 'POST', body: JSON.stringify({ prompt }) }),
  aiExecute: (plan: any, approved = true) => req<any>('/ai/execute', { method: 'POST', body: JSON.stringify({ plan, approved }) }),
  recipes: () => req<any[]>('/ai/recipes'),
  createRecipe: (body: any) => req<any>('/ai/recipes', { method: 'POST', body: JSON.stringify(body) }),
  deleteRecipe: (id: string) => req<any>(`/ai/recipes/${id}`, { method: 'DELETE' }),
  finishes: () => req<any>('/tools/materials'),
  // 导出
  exportUrl: (id: string, fmt: 'svg' | 'dxf' | 'pdf') => `${BASE}/export/${id}/${fmt}`,
  bundleUrl: (projectId: string, fmt: 'svg' | 'dxf' | 'pdf') => `${BASE}/export/project/${projectId}/bundle?fmt=${fmt}`,
}
