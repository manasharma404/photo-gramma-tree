// 3D view: DSM heightmap + draped orthophoto (pipeline/terrain.py), roads draped on top.
// Heights are shown relative to the lowest point: absolute heights carry the error in accuracy.json.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { toUTM, zoneFromCRS } from "./utm.js";

const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "#888";

export async function createThreeView(container, terrainMeta, baseUrl) {
  const meta = terrainMeta;
  const [buf, texture] = await Promise.all([
    fetch(baseUrl + meta.height_file).then((r) => r.arrayBuffer()),
    new THREE.TextureLoader().loadAsync(baseUrl + meta.texture.file),
  ]);
  texture.colorSpace = THREE.SRGBColorSpace;
  const z = new Float32Array(buf);
  const [x0, y0, x1, y1] = meta.bounds_map;
  const W = x1 - x0, H = y1 - y0, nx = meta.width, ny = meta.height;
  const zmin = meta.z_min;

  const scene = new THREE.Scene();
  const sky = new THREE.Color(css("--sand"));
  scene.background = sky;
  const camera = new THREE.PerspectiveCamera(45, 1, 1, 20000);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  const controls = new OrbitControls(camera, renderer.domElement);
  scene.add(new THREE.AmbientLight(0xffffff, 1.0));

  // Plane in metres, centred at the origin; x = east, z = south, y = up.
  const geom = new THREE.PlaneGeometry(W, H, nx - 1, ny - 1);
  geom.rotateX(-Math.PI / 2);
  const pos = geom.attributes.position;
  const base = new Float32Array(pos.count);
  for (let i = 0; i < pos.count; i++) {
    const v = z[i];
    base[i] = Number.isFinite(v) ? v - zmin : 0;
  }
  // Draw only triangles whose corners all have data: no-data areas stay empty, not black walls.
  const idx = [];
  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;
      if (Number.isFinite(z[a]) && Number.isFinite(z[c]) && Number.isFinite(z[b])) idx.push(a, c, b);
      if (Number.isFinite(z[b]) && Number.isFinite(z[c]) && Number.isFinite(z[d])) idx.push(c, d, b);
    }
  }
  geom.setIndex(idx);
  const mesh = new THREE.Mesh(geom, new THREE.MeshBasicMaterial({ map: texture }));
  scene.add(mesh);
  const overlays = new THREE.Group();
  scene.add(overlays);

  let exaggeration = 1.5;
  const applyHeights = () => {
    for (let i = 0; i < pos.count; i++) pos.setY(i, base[i] * exaggeration);
    pos.needsUpdate = true;
    geom.computeBoundingSphere();
    overlays.scale.set(1, exaggeration, 1);
  };
  applyHeights();

  const heightAt = (x, y) => { // map coords -> relative height (bilinear), NaN-safe
    const fx = ((x - x0) / W) * (nx - 1), fy = ((y1 - y) / H) * (ny - 1);
    const i = Math.max(0, Math.min(nx - 2, Math.floor(fx))), j = Math.max(0, Math.min(ny - 2, Math.floor(fy)));
    const tx = fx - i, ty = fy - j;
    const g = (a, b) => (Number.isFinite(z[b * nx + a]) ? base[b * nx + a] : NaN); // no terrain -> no overlay point
    return (g(i, j) * (1 - tx) + g(i + 1, j) * tx) * (1 - ty) + (g(i, j + 1) * (1 - tx) + g(i + 1, j + 1) * tx) * ty;
  };
  const zone = zoneFromCRS(meta.crs);
  const toLocal = ([lon, lat]) => {
    const [ex, ny_] = toUTM(lon, lat, zone);
    return new THREE.Vector3(ex - (x0 + W / 2), heightAt(ex, ny_) + 0.5, -(ny_ - (y0 + H / 2)));
  };

  // Frame the photographed terrain (not the empty grid), three-quarter view from the south.
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, sx = 0, sy = 0, sz = 0, n = 0;
  for (let j = 0; j < ny; j += 4) for (let i = 0; i < nx; i += 4) {
    const k = j * nx + i;
    if (!Number.isFinite(z[k])) continue;
    const x = (i / (nx - 1) - 0.5) * W, zz = (j / (ny - 1) - 0.5) * H;
    minX = Math.min(minX, x); maxX = Math.max(maxX, x); minZ = Math.min(minZ, zz); maxZ = Math.max(maxZ, zz);
    sx += x; sy += base[k]; sz += zz; n++;
  }
  // aim at the centre of mass of the terrain (two separate map pieces would put a bbox centre in empty space)
  const centre = n ? new THREE.Vector3(sx / n, (sy / n) * exaggeration, sz / n) : new THREE.Vector3();
  const size = Math.max(maxX - minX, maxZ - minZ, 50);
  const home = centre.clone().add(new THREE.Vector3(size * 0.2, size * 0.7, size * 0.95));
  camera.position.copy(home);
  controls.target.copy(centre);
  controls.maxPolarAngle = Math.PI * 0.48; // don't go under the ground
  controls.enableDamping = true;
  controls.update();
  scene.fog = new THREE.Fog(sky, size * 1.1, size * 2.6); // edges fade into the sand background

  const resize = () => {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(container);
  resize();
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });

  return {
    setExaggeration(v) { exaggeration = v; applyHeights(); },
    setRoads(fc) {
      overlays.clear();
      for (const f of fc?.features || []) {
        const s = f.properties.status || "unknown";
        const coords = f.geometry.type === "LineString" ? [f.geometry.coordinates] : f.geometry.coordinates;
        for (const line of coords) {
          const pts = line.map(toLocal).filter((p) => Number.isFinite(p.y));
          if (pts.length < 2) continue;
          const mat = s === "partial" || s === "unknown"
            ? new THREE.LineDashedMaterial({ color: css(`--status-${s}`), dashSize: 3, gapSize: 2 })
            : new THREE.LineBasicMaterial({ color: css(`--status-${s}`) });
          const ln = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
          ln.computeLineDistances();
          overlays.add(ln);
        }
      }
    },
    resetView() { camera.position.copy(home); controls.target.copy(centre); },
  };
}
