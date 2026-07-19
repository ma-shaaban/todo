import { useEffect, useState } from "react";

// One page that exercises the backend contract: /api/hello (static),
// /api/db-check (SELECT now() against the platform Postgres) and
// /api/version (the running image version). Replace freely — this is
// scaffolding, not architecture.
function useEndpoint(path) {
  const [state, setState] = useState({ status: "loading", body: null });
  useEffect(() => {
    fetch(path)
      .then(async (res) => {
        const body = await res.json();
        setState({ status: res.ok ? "ok" : `http ${res.status}`, body });
      })
      .catch((err) => setState({ status: "error", body: { detail: String(err) } }));
  }, [path]);
  return state;
}

function Row({ label, result }) {
  return (
    <tr>
      <td style={{ padding: "0.4rem 1rem", fontFamily: "monospace" }}>{label}</td>
      <td style={{ padding: "0.4rem 1rem" }}>{result.status}</td>
      <td style={{ padding: "0.4rem 1rem", fontFamily: "monospace" }}>
        {result.body ? JSON.stringify(result.body) : "…"}
      </td>
    </tr>
  );
}

export default function App() {
  const hello = useEndpoint("/api/hello");
  const dbCheck = useEndpoint("/api/db-check");
  const version = useEndpoint("/api/version");

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", margin: "3rem auto", maxWidth: "48rem" }}>
      <h1>FastAPI + React scaffold</h1>
      <p>
        App version: <strong>{version.body?.version ?? "…"}</strong>
      </p>
      <table style={{ borderCollapse: "collapse", border: "1px solid #ccc" }}>
        <thead>
          <tr>
            <th style={{ padding: "0.4rem 1rem", textAlign: "left" }}>endpoint</th>
            <th style={{ padding: "0.4rem 1rem", textAlign: "left" }}>status</th>
            <th style={{ padding: "0.4rem 1rem", textAlign: "left" }}>response</th>
          </tr>
        </thead>
        <tbody>
          <Row label="/api/hello" result={hello} />
          <Row label="/api/db-check" result={dbCheck} />
          <Row label="/api/version" result={version} />
        </tbody>
      </table>
    </main>
  );
}
