import React, { useState } from "react";

/* spec.props: { code: string, output: string }
   Deterministic notebook: the code is shown verbatim and "Run" reveals the
   recorded output from the spec — no client-side Python, no sandbox to escape. */
export default function Notebook({ code = "", output = "" }) {
  const [ran, setRan] = useState(false);
  return (
    <div className="nb">
      <pre>{code}</pre>
      <div className="run">
        <button onClick={() => setRan(true)}>▶ Run</button>
        <span style={{ fontSize: 11, color: "var(--faint)" }}>deterministic · recorded output</span>
      </div>
      {ran && <div className="out">{output}</div>}
    </div>
  );
}
