import React, { useState } from "react";
import { softmax, heatColor } from "./math.js";

/* spec.props: { rows: number[][], rowSoftmax?: bool, scaleControl?: {label,min,max,init} }
   With rowSoftmax + scaleControl this is the scaled-dot-product attention view:
   each row is divided by sqrt(d) then softmaxed. Without them, raw values. */
export default function Matrix({ rows = [], rowSoftmax = false, scaleControl = null }) {
  const [d, setD] = useState(scaleControl?.init ?? 1);
  const n = rows[0]?.length ?? 0;

  const display = rows.map((r) => {
    const scaled = scaleControl ? r.map((v) => v / Math.sqrt(d)) : r;
    if (!rowSoftmax) {
      const max = Math.max(...rows.flat().map(Math.abs), 1e-9);
      return scaled.map((v) => ({ v, t: Math.abs(v) / max }));
    }
    const p = softmax(scaled, 1);
    return p.map((v) => ({ v, t: v }));
  });

  return (
    <div>
      {scaleControl && (
        <div className="ctl">
          <label>{scaleControl.label}</label>
          <input
            type="range" min={scaleControl.min} max={scaleControl.max} step="1"
            value={d} onChange={(e) => setD(+e.target.value)}
          />
          <span className="val">{d}</span>
        </div>
      )}
      <div className="grid-mx" style={{ gridTemplateColumns: `repeat(${n}, 46px)` }}>
        {display.flat().map((c, i) => (
          <div className="cell" key={i} style={{ background: heatColor(c.t) }}>
            {c.v.toFixed(2)}
          </div>
        ))}
      </div>
    </div>
  );
}
