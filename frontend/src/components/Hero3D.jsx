import { useEffect, useRef } from "react";
import * as THREE from "three";

// A lightweight "systems" object: a Fibonacci-sphere point cloud with a faint
// wireframe icosahedron, rotating slowly. Lazy-loaded (three.js is its own chunk),
// used only on the login / first-run surface — never on the chat or work path.
// Respects reduced-motion, caps DPR, pauses when hidden, and disposes on unmount.
export default function Hero3D() {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = el.clientWidth || 1;
    let h = el.clientHeight || 1;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
    camera.position.z = 3.2;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h);
    el.appendChild(renderer.domElement);

    const raw = getComputedStyle(document.documentElement).getPropertyValue("--nexus-accent").trim();
    const accent = new THREE.Color(raw ? `rgb(${raw.replace(/\s+/g, ",")})` : "#2dd4bf");

    // Fibonacci sphere point cloud
    const N = 1600;
    const positions = new Float32Array(N * 3);
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const t = i * golden;
      positions[i * 3] = Math.cos(t) * r;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = Math.sin(t) * r;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({ color: accent, size: 0.02, transparent: true, opacity: 0.85, depthWrite: false });
    const points = new THREE.Points(geo, mat);
    points.scale.setScalar(1.35);
    scene.add(points);

    const ico = new THREE.LineSegments(
      new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(1.6, 1)),
      new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.1 })
    );
    scene.add(ico);

    let raf = 0;
    let running = false;
    const draw = () => renderer.render(scene, camera);
    const tick = () => {
      points.rotation.y += 0.0016;
      points.rotation.x += 0.0006;
      ico.rotation.y -= 0.0011;
      ico.rotation.x += 0.0004;
      draw();
      raf = requestAnimationFrame(tick);
    };
    const start = () => {
      if (running || reduce) return;
      running = true;
      raf = requestAnimationFrame(tick);
    };
    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };

    if (reduce) draw();
    else start();

    const onVis = () => (document.hidden ? stop() : start());
    const onResize = () => {
      w = el.clientWidth || 1;
      h = el.clientHeight || 1;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      draw();
    };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("resize", onResize);

    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("resize", onResize);
      geo.dispose();
      mat.dispose();
      ico.geometry.dispose();
      ico.material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} className="pointer-events-none absolute inset-0" aria-hidden="true" />;
}
