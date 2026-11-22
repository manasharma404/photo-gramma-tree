// Home hero v7 (22 Nov, 06:45): a concept valley rendered like a relief-printed survey sheet, as a small game board.
// Everything here is an ILLUSTRATION built in code (noise terrain, a landslide scar, a river, a road, villages):
// it is not map data, and the page says so. Pins and routes show what Typhon answers, as a concept.
import * as THREE from "three";

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => t * t * (3 - 2 * t);
const smooth = (a, b, x) => ease(clamp01((x - a) / (b - a)));

// ---------- terrain ----------
function hash(x, y) { const h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return h - Math.floor(h); }
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = ease(xf), v = ease(yf);
  return lerp(lerp(hash(xi, yi), hash(xi + 1, yi), u), lerp(hash(xi, yi + 1), hash(xi + 1, yi + 1), u), v);
}
function fbm(x, y) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < 5; i++) { s += a * vnoise(x * f, y * f); f *= 2.03; a *= 0.5; } return s; }

export const W = 440, D = 300;                                   // board size (x east, z south)
const valleyZ = (x) => 18 * Math.sin(x * 0.011 + 0.4) + 8 * Math.sin(x * 0.029);
const SCAR = { x0: -64, z0: -118, x1: -22, z1: 2 };              // landslide: from the ridge down to the valley

function segDist(px, pz, s) {
  const dx = s.x1 - s.x0, dz = s.z1 - s.z0;
  const t = clamp01(((px - s.x0) * dx + (pz - s.z0) * dz) / (dx * dx + dz * dz));
  return { d: Math.hypot(px - (s.x0 + t * dx), pz - (s.z0 + t * dz)), t };
}

export function height(x, z) {
  const d = z - valleyZ(x);
  let h = 78 * (1 - Math.exp(-((d / 78) ** 2)));                 // the valley between two ridges
  h += 46 * (fbm(x * 0.012 + 3.1, z * 0.012 + 7.7) - 0.35) * (0.35 + 0.65 * smooth(12, 70, Math.abs(d)));
  h += 70 * Math.exp(-((x - 120) ** 2 + (z + 96) ** 2) / (2 * 62 ** 2));   // the big peak
  h += 38 * Math.exp(-((x + 150) ** 2 + (z - 100) ** 2) / (2 * 55 ** 2));
  const s = segDist(x, z, SCAR);                                  // carve the scar, pile a fan at its foot
  h -= 9 * Math.exp(-((s.d / 13) ** 2)) * smooth(0.05, 0.25, s.t) * (1 - smooth(0.8, 1.0, s.t));
  h += 5 * Math.exp(-(((x - SCAR.x1) ** 2 + (z - SCAR.z1 + 4) ** 2) / (2 * 16 ** 2)));
  h -= 3.2 * Math.exp(-((d / 5) ** 2));                            // the river bed
  return (Math.max(h, 0) + 6) * 0.42;                             // low relief, like a printed relief sheet
}

function landColour(x, z, h, slope) {
  const s = segDist(x, z, SCAR);
  const scar = Math.exp(-((s.d / 15) ** 2)) * smooth(0.05, 0.2, s.t) + 0.9 * Math.exp(-(((x - SCAR.x1) ** 2 + (z - SCAR.z1 + 4) ** 2) / (2 * 15 ** 2)));
  const river = Math.exp(-(((z - valleyZ(x)) / 3.2) ** 2));
  const n = fbm(x * 0.05, z * 0.05);
  // relief-print palette: yellow-green lowland → olive → stone on steep ground → pale tops
  const lime = [0.83, 0.87, 0.32], olive = [0.53, 0.64, 0.22], stone = [0.78, 0.74, 0.66], pale = [0.90, 0.88, 0.82];
  let c = lime.map((v, i) => lerp(v, olive[i], smooth(8, 30, h) * 0.9 + (n - 0.5) * 0.35));
  c = c.map((v, i) => lerp(v, stone[i], smooth(0.22, 0.48, slope)));
  c = c.map((v, i) => lerp(v, pale[i], smooth(40, 58, h)));
  c = c.map((v, i) => lerp(v, [0.62, 0.55, 0.45][i] + (n - 0.5) * 0.12, clamp01(scar)));
  c = c.map((v, i) => lerp(v, [0.52, 0.66, 0.70][i], clamp01(river)));
  return c;
}

function buildTerrain(nx = 220, nz = 150) {
  const geo = new THREE.PlaneGeometry(W, D, nx - 1, nz - 1);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position, col = new Float32Array(pos.count * 3);
  const H = new Float32Array(pos.count);
  for (let i = 0; i < pos.count; i++) { H[i] = height(pos.getX(i), pos.getZ(i)); pos.setY(i, H[i]); }
  const dx = W / (nx - 1);
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i);
    const slope = Math.hypot(height(x + dx, z) - height(x - dx, z), height(x, z + dx) - height(x, z - dx)) / (2 * dx);
    col.set(landColour(x, z, H[i], slope), i * 3);
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true }));
  mesh.castShadow = mesh.receiveShadow = true;
  return { mesh, H, nx, nz };
}

// contour lines every `iv` metres, every 5th darker (marching squares on the same grid)
function buildContours({ H, nx, nz }, iv = 3) {
  const pts = [], idx = [];
  const X = (i) => -W / 2 + (i * W) / (nx - 1), Z = (j) => -D / 2 + (j * D) / (nz - 1);
  const at = (i, j) => H[j * nx + i];
  let lo = Infinity, hi = -Infinity; for (const v of H) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  for (let L = Math.ceil(lo / iv) * iv; L < hi; L += iv) {
    const out = (Math.round(L / iv) % 5 === 0) ? idx : pts;
    for (let j = 0; j < nz - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const c = [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]], v = c.map(([a, b]) => at(a, b));
      const cross = [];
      for (let k = 0; k < 4; k++) {
        const a = v[k], b = v[(k + 1) % 4];
        if ((a < L) !== (b < L)) {
          const t = (L - a) / (b - a), [ia, ja] = c[k], [ib, jb] = c[(k + 1) % 4];
          cross.push([lerp(X(ia), X(ib), t), L + 0.25, lerp(Z(ja), Z(jb), t)]);
        }
      }
      if (cross.length >= 2) out.push(...cross[0], ...cross[1]);
      if (cross.length === 4) out.push(...cross[2], ...cross[3]);
    }
  }
  const mk = (arr, color, opacity) => {
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
    return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false }));
  };
  const group = new THREE.Group();
  group.add(mk(pts, 0x6b4f32, 0.28), mk(idx, 0x5a3e24, 0.55));
  return group;
}

// the relief stands on a printed sheet: sides, a paper margin with labels, and a soft shadow
function buildSheet() {
  const g = new THREE.Group();
  const cv = document.createElement("canvas"); cv.width = 1600; cv.height = 1120;
  const c = cv.getContext("2d");
  c.fillStyle = "#EEEBE2"; c.fillRect(0, 0, cv.width, cv.height);
  c.strokeStyle = "rgba(60,50,40,.55)"; c.lineWidth = 2; c.strokeRect(70, 70, cv.width - 140, cv.height - 140);
  c.fillStyle = "rgba(60,50,40,.7)"; c.font = "600 22px ui-monospace, Menlo, Consolas, monospace";
  c.fillText("PROJECT TYPHON · RELIEF CONCEPT", 84, 56); c.textAlign = "right";
  c.fillText("SHEET 01 · ILLUSTRATION", cv.width - 84, 56);
  c.textAlign = "left"; c.font = "500 18px ui-monospace, Menlo, Consolas, monospace";
  c.fillText("NOT MAP DATA · SHAPES MADE IN CODE", 84, cv.height - 36);
  c.textAlign = "right"; c.fillText("CONTOUR INTERVAL 3 · INDEX 15", cv.width - 84, cv.height - 36);
  const tex = new THREE.CanvasTexture(cv); tex.anisotropy = 4;
  const m = 46;
  const paper = new THREE.Mesh(new THREE.PlaneGeometry(W + 2 * m, D + 2 * m), new THREE.MeshLambertMaterial({ map: tex, emissive: 0x504c44, emissiveMap: tex }));
  paper.rotation.x = -Math.PI / 2; paper.position.y = 0; paper.receiveShadow = true;
  g.add(paper);
  // sides of the relief block, cream
  const sideMat = new THREE.MeshLambertMaterial({ color: 0xe4dccb, emissive: 0x4a4538 });
  const n = 120;
  const edge = (fx) => { const p = []; for (let k = 0; k <= n; k++) p.push(fx(k / n)); return p; };
  const edges = [edge((t) => [-W / 2 + t * W, D / 2]), edge((t) => [W / 2, D / 2 - t * D]), edge((t) => [W / 2 - t * W, -D / 2]), edge((t) => [-W / 2, -D / 2 + t * D])];
  for (const e of edges) {
    const pos = [], ind = [];
    e.forEach(([x, z], k) => { pos.push(x, height(x, z), z, x, 0.2, z); if (k) ind.push(2 * k - 2, 2 * k - 1, 2 * k, 2 * k - 1, 2 * k + 1, 2 * k); });
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); geo.setIndex(ind); geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, sideMat); mesh.material.side = THREE.DoubleSide; mesh.castShadow = true; g.add(mesh);
  }
  return g;
}

// clouds: soft billboards made on a canvas, drifting slowly
function cloudTexture() {
  const cv = document.createElement("canvas"); cv.width = cv.height = 256;
  const c = cv.getContext("2d");
  for (let k = 0; k < 26; k++) {
    const x = 128 + (Math.random() - 0.5) * 120, y = 140 + (Math.random() - 0.5) * 60, r = 30 + Math.random() * 46;
    const gr = c.createRadialGradient(x, y, 0, x, y, r);
    gr.addColorStop(0, "rgba(255,255,255,0.55)"); gr.addColorStop(0.6, "rgba(250,250,248,0.25)"); gr.addColorStop(1, "rgba(245,245,242,0)");
    c.fillStyle = gr; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill();
  }
  return new THREE.CanvasTexture(cv);
}
function buildClouds() {
  const tex = cloudTexture(), group = new THREE.Group(), list = [];
  const spots = [[-200, 95, -150, 95], [205, 100, 140, 110], [230, 90, -120, 80], [-235, 88, 135, 90], [40, 105, -185, 75]];
  for (const [x, y, z, s] of spots) {
    const m = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, opacity: 0.88 });
    const sp = new THREE.Sprite(m); sp.position.set(x, y, z); sp.scale.set(s, s * 0.62, 1);
    group.add(sp); list.push({ sp, x0: x, v: 2.5 + Math.random() * 2 });
  }
  return { group, list };
}

// ---------- the story on the board: a road, a blockage, villages, routes ----------
const roadZ = (x) => valleyZ(x) + 13;
function roadPoints(x0, x1, step = 3) { const p = []; for (let x = x0; x <= x1 + 0.01; x += step) p.push(new THREE.Vector3(x, height(x, roadZ(x)) + 0.9, roadZ(x))); return p; }
function trailPoints() {
  // a foot trail over the saddle south of the blockage, from the road to the cut-off village
  const ctrl = [[-70, roadZ(-70)], [-58, 50], [-30, 78], [10, 70], [40, 44], [58, roadZ(58)]];
  const curve = new THREE.CatmullRomCurve3(ctrl.map(([x, z]) => new THREE.Vector3(x, 0, z)));
  return curve.getPoints(90).map((p) => new THREE.Vector3(p.x, height(p.x, p.z) + 1.2, p.z));
}
const BLOCK_X = SCAR.x1;
export const PLACES = {
  base: { x: -170, label: "Base camp", kind: "base" },
  blocked: { x: BLOCK_X, label: "Blocked · debris on the road", kind: "blocked" },
  village: { x: 70, label: "Village cut off by road", kind: "cutoff" },
  landing: { x: 150, dz: -30, label: "Landing zone candidate", kind: "landing" },
  flynext: { x: 155, dz: 40, label: "Fly next · road not seen yet", kind: "flynext" },
};
function placePos(p) { const z = roadZ(p.x) + (p.dz || 0); return new THREE.Vector3(p.x, height(p.x, z), z); }

function villageMesh(cx, n, seed) {
  const g = new THREE.Group(), mat = new THREE.MeshLambertMaterial({ color: 0xf4efe6 }), roof = new THREE.MeshLambertMaterial({ color: 0xc98b7a });
  for (let k = 0; k < n; k++) {
    const a = hash(seed, k) * Math.PI * 2, r = 4 + hash(k, seed) * 14;
    const x = cx + Math.cos(a) * r, z = roadZ(cx) + 6 + Math.sin(a) * r * 0.6;
    const b = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.8, 2.2), hash(k + 3, seed) > 0.5 ? mat : roof);
    b.position.set(x, height(x, z) + 0.9, z); b.rotation.y = a; b.castShadow = true; g.add(b);
  }
  return g;
}

export function createHero(canvas, { still = false, onPins } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(32, 1, 5, 3000);

  scene.add(new THREE.HemisphereLight(0xfbfaf2, 0x8e8a6f, 0.7));
  const sun = new THREE.DirectionalLight(0xfff4dd, 2.3);       // a low sun from the north-west, like a relief print
  sun.position.set(-280, 170, -220); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -300, right: 300, top: 260, bottom: -260, near: 50, far: 900 });
  sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.6;
  scene.add(sun);

  const terrain = buildTerrain();
  scene.add(terrain.mesh, buildContours(terrain), buildSheet());
  scene.add(villageMesh(-170, 16, 1), villageMesh(70, 14, 2), villageMesh(-95, 6, 3));

  // the road: solid along the valley; the stretch under the debris in red
  const roadMat = new THREE.LineBasicMaterial({ color: 0x4b3b2b, transparent: true, opacity: 0.85 });
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(roadPoints(-W / 2 + 4, W / 2 - 4)), roadMat));
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(roadPoints(BLOCK_X - 10, BLOCK_X + 10, 1)),
    new THREE.LineBasicMaterial({ color: 0xd9483b })));

  // routes per vehicle (concept): vehicles stop at the blockage; on foot takes the trail
  const dashMat = new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 3.2, gapSize: 2.4, transparent: true, opacity: 0.95, depthTest: false });
  const mkDash = (pts) => { const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), dashMat); l.computeLineDistances(); l.renderOrder = 5; return l; };
  const toBlock = roadPoints(PLACES.base.x, BLOCK_X - 12, 2);
  const trail = trailPoints();
  const roadOn = roadPoints(58, PLACES.village.x, 2);
  const routes = { vehicle: mkDash(toBlock), foot: mkDash([...roadPoints(PLACES.base.x, -70, 2), ...trail, ...roadOn]) };
  scene.add(routes.vehicle, routes.foot);
  routes.foot.visible = false;
  let flight = [...roadPoints(PLACES.base.x, -70, 3), ...trail, ...roadOn];

  const clouds = buildClouds(); scene.add(clouds.group);

  // camera: oblique, from the south, slightly west; gentle sway and cursor parallax
  const target = new THREE.Vector3(0, 10, 6);
  const view = { az: -0.26, el: 0.9, dist: 820, tx: 0, ty: 0 };
  let zoom = 1, mouseX = 0, mouseY = 0, fly = null;
  const pins = Object.entries(PLACES).map(([id, p]) => ({ id, ...p, pos: placePos(p).add(new THREE.Vector3(0, 2, 0)) }));
  const tmp = new THREE.Vector3();
  let vw = 1, vh = 1;
  function resize() {
    const r = canvas.getBoundingClientRect(); vw = Math.max(1, r.width); vh = Math.max(1, r.height);
    renderer.setSize(vw, vh, false); cam.aspect = vw / vh;
    if (vw >= 900) cam.setViewOffset(vw, vh, -Math.min(0.16 * vw, 230), 0, vw, vh); else cam.clearViewOffset();   // the board sits right of the cards
    cam.updateProjectionMatrix();
  }
  resize(); new ResizeObserver(resize).observe(canvas);
  addEventListener("pointermove", (e) => { mouseX = e.clientX / innerWidth - 0.5; mouseY = e.clientY / innerHeight - 0.5; }, { passive: true });

  const api = {
    setMode(mode) { routes.vehicle.visible = mode !== "foot"; routes.foot.visible = mode === "foot"; },
    zoomBy(f) { zoom = Math.min(1.6, Math.max(0.6, zoom * f)); },
    preview() { if (!still) fly = { t0: performance.now(), dur: 9000 }; },
    frames: 0,
  };

  let raf = 0, visible = true, t0 = performance.now();
  new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) loop(); }).observe(canvas);
  function frame(now) {
    raf = 0;
    if (!visible || document.hidden) return;
    const t = (now - t0) / 1000;
    let az = view.az + (still ? 0 : Math.sin(t * 0.08) * 0.07) + mouseX * 0.12;
    let el = view.el - mouseY * 0.06;
    let tgt = target, dist = view.dist * zoom * (vw < 760 ? 1.25 : 1);
    if (fly) {
      const k = (now - fly.t0) / fly.dur;
      if (k >= 1) fly = null;
      else {
        const e = ease(Math.min(1, k * 1.15)), p = flight[Math.min(flight.length - 1, Math.floor(e * (flight.length - 1)))];
        const mix = Math.sin(Math.PI * Math.min(1, k)) ;
        tgt = target.clone().lerp(p, mix); dist = lerp(dist, 210, mix); el = lerp(el, 0.55, mix); az = lerp(az, -0.1, mix);
      }
    }
    cam.position.set(tgt.x + Math.sin(az) * Math.cos(el) * dist, tgt.y + Math.sin(el) * dist, tgt.z + Math.cos(az) * Math.cos(el) * dist);
    cam.lookAt(tgt);
    for (const c of clouds.list) { c.sp.position.x = ((c.x0 + t * c.v + W) % (2 * W)) - W; }
    renderer.render(scene, cam);
    // pins: project to the screen for the HTML layer
    if (onPins) onPins(pins.map((p) => { tmp.copy(p.pos).project(cam); return { id: p.id, x: (tmp.x * 0.5 + 0.5) * vw, y: (-tmp.y * 0.5 + 0.5) * vh, on: tmp.z < 1 }; }));
    api.frames++;
    raf = requestAnimationFrame(frame);
  }
  function loop() { if (!raf && visible && !document.hidden) raf = requestAnimationFrame(frame); }
  document.addEventListener("visibilitychange", loop);
  loop();
  return api;
}
