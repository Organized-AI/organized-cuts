import React, { useEffect, useRef, useState } from "react";

// Named curve library — specs reference functions by name (deterministic; no eval).
const FNS = {
  relu: (x) => Math.max(0, x),
  tanh: (x) => Math.tanh(x),
  sigmoid: (x) => 1 / (1 + Math.exp(-x)),
  gelu: (x) => 0.5 * x * (1 + Math.tanh(Math.sqrt(2 / Math.PI) * (x + 0.044715 * x ** 3))),
  silu: (x) => x / (1 + Math.exp(-x)),
  sin: Math.sin,
  cos: Math.cos,
  exp: (x) => Math.exp(x),
  log: (x) => (x > 0 ? Math.log(x) : NaN),
  square: (x) => x * x,
};

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/* spec.props: { fns: string[], xRange?: [a,b], yRange?: [a,b] } */
export default function Plot({ fns = ["gelu"], xRange = [-5, 5], yRange = [-2, 4] }) {
  const known = fns.filter((f) => FNS[f.toLowerCase()]);
  const [fn, setFn] = useState(known[0] ?? "gelu");
  const ref = useRef(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    const W = cv.width, H = cv.height;
    const [x0, x1] = xRange, [y0, y1] = yRange;
    const px = (x) => ((x - x0) / (x1 - x0)) * W;
    const py = (y) => H - ((y - y0) / (y1 - y0)) * H;
    ctx.clearRect(0, 0, W, H);
    // grid
    ctx.strokeStyle = cssVar("--border"); ctx.lineWidth = 1;
    for (let gx = Math.ceil(x0); gx <= x1; gx++) { ctx.beginPath(); ctx.moveTo(px(gx), 0); ctx.lineTo(px(gx), H); ctx.stroke(); }
    for (let gy = Math.ceil(y0); gy <= y1; gy++) { ctx.beginPath(); ctx.moveTo(0, py(gy)); ctx.lineTo(W, py(gy)); ctx.stroke(); }
    // axes
    ctx.strokeStyle = cssVar("--border-bright"); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(0, py(0)); ctx.lineTo(W, py(0)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px(0), 0); ctx.lineTo(px(0), H); ctx.stroke();
    // curve
    const f = FNS[fn.toLowerCase()];
    ctx.strokeStyle = cssVar("--accent"); ctx.lineWidth = 2.5; ctx.beginPath();
    let started = false;
    for (let i = 0; i <= W; i++) {
      const x = x0 + (i / W) * (x1 - x0);
      const y = f(x);
      if (!Number.isFinite(y)) { started = false; continue; }
      const yy = py(y);
      if (!started) { ctx.moveTo(i, yy); started = true; } else ctx.lineTo(i, yy);
    }
    ctx.stroke();
    ctx.fillStyle = cssVar("--muted");
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillText(`${fn}(x)`, 12, 18);
  }, [fn, xRange, yRange]);

  return (
    <div>
      {known.length > 1 && (
        <div className="ctl">
          <label>function</label>
          <select value={fn} onChange={(e) => setFn(e.target.value)}>
            {known.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      )}
      <canvas ref={ref} width={520} height={240} />
    </div>
  );
}
