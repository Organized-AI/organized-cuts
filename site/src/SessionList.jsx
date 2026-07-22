import React, { useEffect, useState } from "react";
import { fmtDur } from "./time.js";

export default function SessionList() {
  const [sessions, setSessions] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}sessions/index.json`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setSessions)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="err">Couldn't load sessions ({err}).</div>;
  if (!sessions) return <div className="loading">loading sessions…</div>;

  return (
    <div className="s-grid">
      {sessions.map((s) => (
        <a key={s.name} className="s-card" href={`#/s/${s.name}`}>
          <h3>{s.title}</h3>
          <div className="meta">
            <span>{s.speaker}</span>
            <span>{fmtDur(s.duration)}</span>
            <span>{s.chapters} chapters</span>
            {s.widgets > 0 && <span className="w">{s.widgets} widgets</span>}
          </div>
        </a>
      ))}
    </div>
  );
}
