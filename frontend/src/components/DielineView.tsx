import { useMemo } from 'react'
import type { DielineData } from '../fold3d'

/** 生成 2D 刀模 SVG 字符串 */
export function dielineToSvg(dl: DielineData, w = 520, h = 480): string {
  const margin = 16
  const scale = Math.min((w - margin * 2) / (dl.flatWidth || 1), (h - margin * 2) / (dl.flatHeight || 1), 4)
  const offX = margin + ((w - margin * 2) - dl.flatWidth * scale) / 2
  const offY = margin + ((h - margin * 2) - dl.flatHeight * scale) / 2

  const px = (x: number) => (offX + x * scale).toFixed(2)
  const py = (y: number) => (offY + (dl.flatHeight - y) * scale).toFixed(2) // Y 翻转

  const path = (pts: [number, number][], closed = true) =>
    'M ' + pts.map(p => `${px(p[0])} ${py(p[1])}`).join(' L ') + (closed ? ' Z' : '')

  const parts: string[] = []
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">`)
  parts.push(`<rect width="${w}" height="${h}" fill="#fff"/>`)

  const colors: Record<string, string> = {
    front: '#dbeafe', back: '#dbeafe', left: '#e0e7ff', right: '#e0e7ff',
    tuck: '#fef3c7', dust: '#fef9c3', glue: '#f3e8ff', lid: '#dcfce7',
    lock: '#ffedd5', wing: '#ffedd5', base: '#f1f5f9', wall: '#e2e8f0',
    tray: '#d1fae5', sleeve: '#d1fae5', divider: '#fce7f3', shelf: '#f5f3ff',
    bottom: '#fef3c7', handle: '#fce7f3',
  }

  for (const piece of dl.pieces) {
    for (const spec of Object.values(piece.panels)) {
      const fill = colors[spec.role] || '#f1f5f9'
      parts.push(`<path d="${path(spec.points)}" fill="${fill}" stroke="#e11d48" stroke-width="1"/>`)
      for (const hole of spec.holes) {
        parts.push(`<path d="${path(hole)}" fill="#fff" stroke="#e11d48" stroke-width="1"/>`)
      }
    }
  }

  // 折痕线
  const seen = new Set<string>()
  for (const piece of dl.pieces) {
    for (const f of piece.folds) {
      const pa = piece.panels[f.a], pb = piece.panels[f.b]
      if (!pa || !pb) continue
      const e = sharedEdgeOf(pa.points, pb.points)
      if (!e) continue
      const k = [e[0][0], e[0][1], e[1][0], e[1][1]].map(v => Math.round(v * 10)).join(',')
      if (seen.has(k)) continue
      seen.add(k)
      parts.push(`<line x1="${px(e[0][0])}" y1="${py(e[0][1])}" x2="${px(e[1][0])}" y2="${py(e[1][1])}" stroke="#2563eb" stroke-width="1" stroke-dasharray="4,2"/>`)
    }
  }

  // 标签
  for (const piece of dl.pieces) {
    for (const spec of Object.values(piece.panels)) {
      const cx = spec.points.reduce((s, p) => s + p[0], 0) / spec.points.length
      const cy = spec.points.reduce((s, p) => s + p[1], 0) / spec.points.length
      parts.push(`<text x="${px(cx)}" y="${py(cy)}" font-size="9" text-anchor="middle" fill="#334155" font-family="sans-serif">${spec.name}</text>`)
    }
  }

  parts.push(`<text x="8" y="${h - 6}" font-size="10" fill="#94a3b8">展开 ${dl.flatWidth} × ${dl.flatHeight} mm · 红色=切割线 蓝色虚线=折痕线</text>`)
  parts.push('</svg>')
  return parts.join('\n')
}

function edgeKey(a: [number, number], b: [number, number]): string {
  const q = (n: number) => Math.round(n / 1e-3)
  const ax = q(a[0]), ay = q(a[1]), bx = q(b[0]), by = q(b[1])
  return (ax < bx || (ax === bx && ay <= by)) ? `${ax},${ay}|${bx},${by}` : `${bx},${by}|${ax},${ay}`
}

function sharedEdgeOf(pa: [number, number][], pb: [number, number][]): [[number, number], [number, number]] | null {
  const set = new Set<string>()
  for (let i = 0; i < pa.length; i++) set.add(edgeKey(pa[i], pa[(i + 1) % pa.length]))
  for (let i = 0; i < pb.length; i++) {
    const k = edgeKey(pb[i], pb[(i + 1) % pb.length])
    if (set.has(k)) return [pb[i], pb[(i + 1) % pb.length]]
  }
  return null
}

export default function DielineView({ dl, width, height }: { dl: DielineData; width?: number; height?: number }) {
  const svg = useMemo(() => dielineToSvg(dl, width ?? 520, height ?? 460), [dl, width, height])
  return <div className="canvas-box" dangerouslySetInnerHTML={{ __html: svg }} />
}
