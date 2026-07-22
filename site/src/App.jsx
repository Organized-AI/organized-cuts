import React, { useEffect, useState } from "react";
import SessionList from "./SessionList.jsx";
import SessionPage from "./SessionPage.jsx";

// Tiny hash router: "#/" = list, "#/s/<name>" = session page.
function parseHash() {
  const m = window.location.hash.match(/^#\/s\/([\w-]+)/);
  return m ? { page: "session", name: m[1] } : { page: "list" };
}

export default function App() {
  const [route, setRoute] = useState(parseHash);
  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="wrap">
      <header className="masthead">
        <a className="mark" href="#/">OAI</a>
        <div>
          <h1>Organized Cuts · Recordings</h1>
          <div className="sub">recordings.organizedai.vip</div>
        </div>
      </header>
      {route.page === "session"
        ? <SessionPage name={route.name} />
        : <SessionList />}
    </div>
  );
}
