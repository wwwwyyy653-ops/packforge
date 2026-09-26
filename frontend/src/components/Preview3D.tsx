import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { fold3D, type DielineData, type Face3D, type P3 } from '../fold3d'

const ROLE_COLORS: Record<string, number> = {
  front: 0x93c5fd, back: 0x93c5fd, left: 0xa5b4fc, right: 0xa5b4fc,
  tuck: 0xfcd34d, dust: 0xfde047, glue: 0xd8b4fe, lid: 0x86efac,
  lock: 0xfdba74, wing: 0xfdba74, base: 0xcbd5e1, wall: 0xe2e8f0,
  tray: 0x6ee7b7, sleeve: 0x6ee7b7, divider: 0xf9a8d4, shelf: 0xc4b5fd,
  bottom: 0xfcd34d, handle: 0xf9a8d4,
}

function shapeFromPts(pts: P3[]): THREE.Shape {
  const shape = new THREE.Shape()
  if (pts.length < 3) return shape
  shape.moveTo(pts[0][0], pts[0][1])
  for (let i = 1; i < pts.length; i++) shape.lineTo(pts[i][0], pts[i][1])
  shape.closePath()
  return shape
}

export default function Preview3D({ dl }: { dl: DielineData }) {
  const mountRef = useRef<HTMLDivElement>(null)
  const [progress, setProgress] = useState(1)
  const progressRef = useRef(1)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const meshesRef = useRef<THREE.Mesh[]>([])
  const edgesRef = useRef<THREE.LineSegments[]>([])

  useEffect(() => {
    if (!mountRef.current) return
    const mount = mountRef.current
    const w = mount.clientWidth || 520
    const h = mount.clientHeight || 460

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(w, h)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)
    rendererRef.current = renderer

    const scene = new THREE.Scene()
    sceneRef.current = scene
    scene.background = new THREE.Color(0xf8fafc)

    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000)
    camera.position.set(320, 260, 420)
    cameraRef.current = camera

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controlsRef.current = controls

    const hemi = new THREE.HemisphereLight(0xffffff, 0x94a3b8, 1.1)
    scene.add(hemi)
    const dir = new THREE.DirectionalLight(0xffffff, 1.6)
    dir.position.set(300, 400, 200)
    scene.add(dir)
    const dir2 = new THREE.DirectionalLight(0xffffff, 0.6)
    dir2.position.set(-200, -100, -300)
    scene.add(dir2)
    const grid = new THREE.GridHelper(600, 12, 0xcbd5e1, 0xe2e8f0)
    scene.add(grid)

    let raf = 0
    const loop = () => {
      raf = requestAnimationFrame(loop)
      controls.update()
      renderer.render(scene, camera)
    }
    loop()

    const onResize = () => {
      const w2 = mount.clientWidth, h2 = mount.clientHeight
      renderer.setSize(w2, h2)
      camera.aspect = w2 / h2
      camera.updateProjectionMatrix()
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      meshesRef.current.forEach(m => { scene.remove(m); m.geometry.dispose(); (m.material as THREE.Material).dispose() })
      edgesRef.current.forEach(e => { scene.remove(e); e.geometry.dispose(); (e.material as THREE.Material).dispose() })
      meshesRef.current = []
      edgesRef.current = []
      controls.dispose()
      renderer.dispose()
      if (renderer.domElement.parentElement === mount) mount.removeChild(renderer.domElement)
    }
  }, [])

  useEffect(() => {
    const scene = sceneRef.current
    if (!scene || !dl) return
    meshesRef.current.forEach(m => { scene.remove(m); m.geometry.dispose(); (m.material as THREE.Material).dispose() })
    edgesRef.current.forEach(e => { scene.remove(e); e.geometry.dispose(); (e.material as THREE.Material).dispose() })
    meshesRef.current = []
    edgesRef.current = []

    const pieces = dl.pieces
    const offsets: P3[] = []
    if (pieces.length > 1) {
      const gap = 60
      for (let i = 0; i < pieces.length; i++) offsets.push([0, 0, i * gap])
    }
    const faces = fold3D(dl, progressRef.current, offsets)

    let minX = Infinity, minY = Infinity, minZ = Infinity
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity
    for (const f of faces) {
      for (const p of f.points) {
        minX = Math.min(minX, p[0]); minY = Math.min(minY, p[1]); minZ = Math.min(minZ, p[2])
        maxX = Math.max(maxX, p[0]); maxY = Math.max(maxY, p[1]); maxZ = Math.max(maxZ, p[2])
      }
    }
    if (isFinite(minX)) {
      const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2
      const size = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 10)
      const cam = cameraRef.current
      if (cam) {
        cam.position.set(cx + size * 0.9, cy + size * 0.75, cz + size * 1.1)
        cam.lookAt(cx, cy, cz)
        controlsRef.current?.target.set(cx, cy, cz)
        controlsRef.current?.update()
      }
    }

    const group = new THREE.Group()
    for (const f of faces) {
      const shape = shapeFromPts(f.points)
      if (shape.getPoints().length < 3) continue
      const geo = new THREE.ShapeGeometry(shape)
      const color = ROLE_COLORS[f.role] ?? 0x94a3b8
      const mat = new THREE.MeshStandardMaterial({
        color, side: THREE.DoubleSide, roughness: 0.65, metalness: 0.05,
        transparent: true, opacity: f.role === 'tuck' ? 0.85 : 0.97,
      })
      const mesh = new THREE.Mesh(geo, mat)
      group.add(mesh)
      meshesRef.current.push(mesh)

      const pts = f.points.map(p => new THREE.Vector3(p[0], p[1], 0.4))
      const lineGeo = new THREE.BufferGeometry().setFromPoints(pts)
      const lineMat = new THREE.LineBasicMaterial({ color: 0x1e293b, linewidth: 1 })
      const line = new THREE.LineLoop(lineGeo, lineMat)
      group.add(line)
      edgesRef.current.push(line as unknown as THREE.LineSegments)

      for (const hole of f.holes) {
        const hShape = shapeFromPts(hole)
        const hGeo = new THREE.ShapeGeometry(hShape)
        const hMesh = new THREE.Mesh(hGeo, new THREE.MeshStandardMaterial({
          color: 0xf8fafc, side: THREE.DoubleSide, roughness: 0.9,
        }))
        hMesh.position.z = 0.25
        group.add(hMesh)
        meshesRef.current.push(hMesh)
      }
    }
    scene.add(group)
  }, [dl])

  const handleProgress = (v: number) => {
    setProgress(v)
    progressRef.current = v
    const scene = sceneRef.current
    if (!scene) return
    meshesRef.current.forEach(m => { scene.remove(m); m.geometry.dispose(); (m.material as THREE.Material).dispose() })
    edgesRef.current.forEach(e => { scene.remove(e); e.geometry.dispose(); (e.material as THREE.Material).dispose() })
    meshesRef.current = []
    edgesRef.current = []
    const pieces = dl.pieces
    const offsets: P3[] = []
    if (pieces.length > 1) for (let i = 0; i < pieces.length; i++) offsets.push([0, 0, i * 60])
    const faces = fold3D(dl, v, offsets)
    const group = new THREE.Group()
    for (const f of faces) {
      const shape = shapeFromPts(f.points)
      if (shape.getPoints().length < 3) continue
      const geo = new THREE.ShapeGeometry(shape)
      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
        color: ROLE_COLORS[f.role] ?? 0x94a3b8, side: THREE.DoubleSide,
        roughness: 0.65, metalness: 0.05, transparent: true,
        opacity: f.role === 'tuck' ? 0.85 : 0.97,
      }))
      group.add(mesh); meshesRef.current.push(mesh)
      const line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
        f.points.map(p => new THREE.Vector3(p[0], p[1], 0.4))),
        new THREE.LineBasicMaterial({ color: 0x1e293b }))
      group.add(line); edgesRef.current.push(line as unknown as THREE.LineSegments)
      for (const hole of f.holes) {
        const hm = new THREE.Mesh(new THREE.ShapeGeometry(shapeFromPts(hole)),
          new THREE.MeshStandardMaterial({ color: 0xf8fafc, side: THREE.DoubleSide }))
        hm.position.z = 0.25
        group.add(hm); meshesRef.current.push(hm)
      }
    }
    scene.add(group)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>
      <div ref={mountRef} style={{ flex: 1, minHeight: 400, borderRadius: 12, overflow: 'hidden', border: '1px solid var(--line)', background: '#f8fafc' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>折叠进度</span>
        <input type="range" min={0} max={1} step={0.01} value={progress}
          onChange={e => handleProgress(parseFloat(e.target.value))}
          style={{ flex: 1 }} />
        <span style={{ fontSize: 12, minWidth: 38, textAlign: 'right' }}>{Math.round(progress * 100)}%</span>
      </div>
      <div className="muted" style={{ fontSize: 11 }}>
        拖拽旋转 · 滚轮缩放 · 滑块控制折叠动画 · 两件套沿 Z 轴分离显示
      </div>
    </div>
  )
}
