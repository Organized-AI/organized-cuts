import React, { useState } from "react";
import { softmax } from "./math.js";

/* spec.props: { labels: string[], logits: number[], tempRange?: [min,max] } */
export default function Softmax({ labels = [], logits = [], tempRange = [0.2, 3] }) {
  const [T, setT] = useState(1);
  const p = softmax(logits, T);
  return (
    <div>
      <div className="ctl">
        <label>temperature T</label>
        <input
          type="range" min={tempRange[0]} max={tempRange[1]} step="0.05"
          value={T} onChange={(e) => setT(+e.target.value)}
        />
        <span className="val">{T.toFixed(2)}</span>
      </div>
      <div className="bars">
        {labels.map((lb, i) => (
          <div className="row" key={i}>
            <span className="lab">{lb}</span>
            <div className="track"><i style={{ width: `${(p[i] * 100).toFixed(1)}%` }} /></div>
            <span className="pct">{(p[i] * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
