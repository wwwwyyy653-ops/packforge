/** 客户端 3D 折叠计算（与后端 folding.py 同构） */

export type P2 = [number, number]
export type P3 = [number, number, number]

export interface PanelSpec {
  id: string
  role: string
  name: string
  points: P2[]
  holes: P2[][]
  extra?: Record<string, any>
}

export interface FoldSpec {
  a: string
  b: string
  angle: number
}

export interface Piece {
  label: string
  panels: Record<string, PanelSpec>
  folds: FoldSpec[]
}

export interface DielineData {
  boxType: string
  label: string
  flatWidth: number
  flatHeight: number
  twoPiece: boolean
  pieces: Piece[]
}

export interface Face3D {
  id: string
  role: string
  name: string
  points: P3[]
  holes: P3[][]
  piece: number
}

function sub(a: P3, b: P3): P3 { return [a[0]-b[0], a[1]-b[1], a[2]-b[2]] }
function norm(a: P3): number { return Math.sqrt(a[0]**2 + a[1]**2 + a[2]**2) }
function unit(a: P3): P3 { const n = norm(a); return n < 1e-12 ? [0,0,1] : [a[0]/n, a[1]/n, a[2]/n] }
function cross(a: P3, b: P3): P3 {
  return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
}

export interface Basis { O: P3; u: P3; v: P3; n: P3 }
const ZERO: Basis = { O: [0,0,0], u: [1,0,0], v: [0,1,0], n: [0,0,1] }

function applyBasis(b: Basis, p: P2): P3 {
  return [b.O[0]+b.u[0]*p[0]+b.v[0]*p[1],
          b.O[1]+b.u[1]*p[0]+b.v[1]*p[1],
          b.O[2]+b.u[2]*p[0]+b.v[2]*p[1]]
}

function childBasis(parent: Basis, ha: P2, hb: P2, thetaDeg: number): Basis {
  const a3 = applyBasis(parent, ha)
  const b3 = applyBasis(parent, hb)
  const u = unit(sub(b3, a3))
  const vc = cross(parent.n, u)
  const s = Math.cos(thetaDeg * Math.PI / 180)
  const si = Math.sin(thetaDeg * Math.PI / 180)
  const uC = u
  const vC: P3 = [vc[0]*s + parent.n[0]*si, vc[1]*s + parent.n[1]*si, vc[2]*s + parent.n[2]*si]
  const nC: P3 = [parent.n[0]*s - vc[0]*si, parent.n[1]*s - vc[1]*si, parent.n[2]*s - vc[2]*si]
  const O: P3 = [a3[0]-uC[0]*ha[0]-vC[0]*ha[1],
                 a3[1]-uC[1]*ha[0]-vC[1]*ha[1],
                 a3[2]-uC[2]*ha[0]-vC[2]*ha[1]]
  return { O, u: uC, v: vC, n: nC }
}

function polyArea(p: P2[]): number {
  let s = 0
  for (let i = 0; i < p.length; i++) {
    const [x1,y1] = p[i], [x2,y2] = p[(i+1)%p.length]
    s += x1*y2 - x2*y1
  }
  return s/2
}

function edgeKey(a: P2, b: P2): string {
  const q = (n: number) => Math.round(n/1e-3)
  const ax=q(a[0]), ay=q(a[1]), bx=q(b[0]), by=q(b[1])
  return (ax < bx || (ax===bx && ay<=by)) ? `${ax},${ay}|${bx},${by}` : `${bx},${by}|${ax},${ay}`
}

function sharedEdge(pa: P2[], pb: P2[]): [P2, P2] | null {
  const set = new Set<string>()
  for (let i = 0; i < pa.length; i++) set.add(edgeKey(pa[i], pa[(i+1)%pa.length]))
  for (let i = 0; i < pb.length; i++) {
    const k = edgeKey(pb[i], pb[(i+1)%pb.length])
    if (set.has(k)) return [pb[i], pb[(i+1)%pb.length]]
  }
  return null
}

function center(p: P2[]): P2 {
  let x = 0, y = 0
  for (const [a,b] of p) { x += a; y += b }
  return [x/p.length, y/p.length]
}

/**
 * 计算给定折叠进度下所有面板的 3D 顶点。
 * pieceOffsets: 各片在 3D 空间中的摆放偏移（两件套分开显示）
 */
export function fold3D(dl: DielineData, progress: number, pieceOffsets: P3[] = []): Face3D[] {
  const out: Face3D[] = []
  dl.pieces.forEach((piece, pi) => {
    const panels = piece.panels
    const keys = Object.keys(panels)
    if (keys.length === 0) return
    const adj: Record<string, [string, number, P2, P2][]> = {}
    keys.forEach(k => adj[k] = [])
    for (const f of piece.folds) {
      if (!panels[f.a] || !panels[f.b]) continue
      const e = sharedEdge(panels[f.a].points, panels[f.b].points)
      if (!e) continue
      const [ha, hb] = e
      const ca = center(panels[f.a].points)
      const cb = center(panels[f.b].points)
      let ux = hb[0]-ha[0], uy = hb[1]-ha[1]
      const ul = Math.hypot(ux, uy) || 1
      ux /= ul; uy /= ul
      let vx = -uy, vy = ux
      const sb = (cb[0]-ha[0])*vx + (cb[1]-ha[1])*vy
      if (sb < 0) { vx = -vx; vy = -vy }
      adj[f.a].push([f.b, f.angle, ha, hb])
      adj[f.b].push([f.a, f.angle, ha, hb])
    }
    let root = keys[0]
    let maxA = -Infinity
    for (const k of keys) {
      const a = Math.abs(polyArea(panels[k].points))
      if (a > maxA) { maxA = a; root = k }
    }
    const basis: Record<string, Basis> = { [root]: ZERO }
    const order = [root]
    const visited = new Set([root])
    while (order.length) {
      const cur = order.shift()!
      for (const [nxt, ang, ha, hb] of adj[cur]) {
        if (visited.has(nxt)) continue
        visited.add(nxt)
        basis[nxt] = childBasis(basis[cur], ha, hb, ang * progress)
        order.push(nxt)
      }
    }
    const off: P3 = pieceOffsets[pi] || [0, 0, 0]
    for (const k of keys) {
      const spec = panels[k]
      const b = basis[k] || ZERO
      const pts = spec.points.map(p => {
        const w = applyBasis(b, p)
        return [w[0]+off[0], w[1]+off[1], w[2]+off[2]] as P3
      })
      const holes = spec.holes.map(h => h.map(p => {
        const w = applyBasis(b, p)
        return [w[0]+off[0], w[1]+off[1], w[2]+off[2]] as P3
      }))
      out.push({ id: k, role: spec.role, name: spec.name, points: pts, holes, piece: pi })
    }
  })
  return out
}
