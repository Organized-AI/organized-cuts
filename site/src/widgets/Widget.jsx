import React from "react";
import { fmtDur } from "../time.js";
import Softmax from "./Softmax.jsx";
import Matrix from "./Matrix.jsx";
import Plot from "./Plot.jsx";
import Notebook from "./Notebook.jsx";

// Deterministic widget kit (8kEdu-style): a JSON concept spec picks a renderer
// from this registry. Unknown types degrade to a labeled fallback so a session
// authored against a newer kit never crashes an older viewer.
const REGISTRY = {
  softmax: Softmax,
  matrix: Matrix,
  plot: Plot,
  notebook: Notebook,
};

export default function Widget({ spec, active, onSeek }) {
  const Impl = REGISTRY[spec.type];
  return (
    <div className={"widget" + (active ? " now" : "")}>
      <div className="w-head">
        <span className="k">// {spec.kind ?? spec.type}</span>
        <h4>{spec.title ?? spec.type}</h4>
        <button className="w-ts" onClick={onSeek} title={`Jump to ${fmtDur(spec.t)}`}>
          @ {fmtDur(spec.t)}
        </button>
      </div>
      <div className="w-body">
        {spec.caption && <p className="cap">{spec.caption}</p>}
        {Impl
          ? <Impl {...(spec.props ?? {})} />
          : <div className="w-fallback">unsupported widget type: “{spec.type}”</div>}
      </div>
    </div>
  );
}
