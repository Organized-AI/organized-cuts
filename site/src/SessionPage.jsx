import React, { useEffect, useMemo, useRef, useState } from "react";
import Widget from "./widgets/Widget.jsx";
import { fmtDur } from "./time.js";

const PREF_KEY = "oai.session.layout";
const LAYOUTS = ["tabs", "companion"]; // C (default) and A

function loadLayoutPref() {
  try {
    const v = localStorage.getItem(PREF_KEY);
    return LAYOUTS.includes(v) ? v : "tabs";
  } catch {
    return "tabs";
  }
}

export default function SessionPage({ name }) {
  const [session, setSession] = useState(null);
  const [err, setErr] = useState(null);
  const [layout, setLayout] = useState(loadLayoutPref);
  const [time, setTime] = useState(0);
  const videoRef = useRef(null);

  useEffect(() => {
    setSession(null); setErr(null);
    fetch(`${import.meta.env.BASE_URL}sessions/${name}/session.json`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setSession)
      .catch((e) => setErr(String(e)));
  }, [name]);

  function pickLayout(l) {
    setLayout(l);
    try { localStorage.setItem(PREF_KEY, l); } catch { /* private mode */ }
  }

  function seek(t) {
    const v = videoRef.current;
    if (v) { v.currentTime = t; v.play?.(); }
    setTime(t);
  }

  if (err) return <div className="err">Couldn't load session “{name}” ({err}).</div>;
  if (!session) return <div className="loading">loading session…</div>;

  const widgets = session.widgets ?? [];

  return (
    <div>
      <a className="crumb" href="#/">← all sessions</a>
      <div className="s-head" style={{ marginTop: 10 }}>
        <div>
          <h2 className="s-title">{session.title}</h2>
          <div className="s-meta">
            <span>{session.speaker}</span>
            <span>·</span>
            <span>{fmtDur(session.duration)}</span>
            <span>·</span>
            <span>{session.chapters.length} chapters</span>
            {widgets.length > 0 && <><span>·</span><span>{widgets.length} widgets</span></>}
          </div>
        </div>
        <div className="layout-toggle" role="group" aria-label="Layout">
          <button aria-pressed={layout === "tabs"} onClick={() => pickLayout("tabs")}>Widgets tab</button>
          <button aria-pressed={layout === "companion"} onClick={() => pickLayout("companion")}>Companion</button>
        </div>
      </div>

      {layout === "companion"
        ? <Companion session={session} time={time} setTime={setTime} seek={seek} videoRef={videoRef} />
        : <Tabs session={session} time={time} setTime={setTime} seek={seek} videoRef={videoRef} />}
    </div>
  );
}

/* ---------------- shared pieces ---------------- */

function Player({ session, videoRef, setTime }) {
  return (
    <div className="player">
      {session.media_url ? (
        <video
          ref={videoRef}
          src={session.media_url}
          controls
          playsInline
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        />
      ) : (
        <div className="placeholder">
          // no media_url in project.json — chapters &amp; widgets below still work
        </div>
      )}
    </div>
  );
}

function Chapters({ session, time, seek }) {
  return (
    <div className="chapters">
      {session.chapters.map((c) => (
        <button
          key={c.id}
          className={time >= c.start && time < c.end ? "active" : ""}
          onClick={() => seek(c.start)}
          title={c.caption}
        >
          {fmtDur(c.start)} · {c.title}
        </button>
      ))}
    </div>
  );
}

function Transcript({ session, time, seek }) {
  return (
    <div className="transcript">
      {session.transcript.map((s, i) => (
        <p key={i} className={time >= s.start && time < s.end ? "now" : ""} onClick={() => seek(s.start)}>
          <span className="t">{fmtDur(s.start)}</span>
          {s.text}
        </p>
      ))}
      {session.transcript.length === 0 && (
        <p style={{ cursor: "default" }}>No transcript for this session yet.</p>
      )}
    </div>
  );
}

function WidgetCards({ widgets, time, seek }) {
  if (widgets.length === 0) {
    return <div className="loading">No widgets for this session yet — add a widgets.json next to project.json and re-run 07_session_data.py.</div>;
  }
  // "current" widget = last one whose timestamp has passed
  const currentIdx = widgets.reduce((acc, w, i) => (time >= w.t ? i : acc), -1);
  return widgets.map((w, i) => (
    <Widget key={i} spec={w} active={i === currentIdx} onSeek={() => seek(w.t)} />
  ));
}

/* ---------------- layout C: widgets tab (default) ---------------- */

function Tabs({ session, time, setTime, seek, videoRef }) {
  const tabs = useMemo(() => ([
    { id: "widgets", label: "Widgets", count: (session.widgets ?? []).length },
    { id: "transcript", label: "Transcript", count: null },
    { id: "chapters", label: "Chapters", count: session.chapters.length },
  ]), [session]);
  const [tab, setTab] = useState("widgets");

  return (
    <div>
      <Player session={session} videoRef={videoRef} setTime={setTime} />
      <Chapters session={session} time={time} seek={seek} />
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label} {t.count != null && <span className="c">{t.count}</span>}
          </button>
        ))}
      </div>
      <div className="pane">
        {tab === "widgets" && (
          <div className="w-grid">
            <WidgetCards widgets={session.widgets ?? []} time={time} seek={seek} />
          </div>
        )}
        {tab === "transcript" && <Transcript session={session} time={time} seek={seek} />}
        {tab === "chapters" && (
          <div className="transcript">
            {session.chapters.map((c) => (
              <p key={c.id} onClick={() => seek(c.start)}>
                <span className="t">{fmtDur(c.start)}</span>{c.title}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------- layout A: companion panel ---------------- */

function Companion({ session, time, setTime, seek, videoRef }) {
  return (
    <div className="lay-companion">
      <div className="left">
        <Player session={session} videoRef={videoRef} setTime={setTime} />
        <Chapters session={session} time={time} seek={seek} />
      </div>
      <div className="rail">
        <div className="rail-head">
          <span>Interactive widgets</span>
          <span>synced to {fmtDur(time)}</span>
        </div>
        <WidgetCards widgets={session.widgets ?? []} time={time} seek={seek} />
      </div>
    </div>
  );
}
