import { useState, useEffect } from "react";
import Chat from "./components/Chat";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/status`)
      .then((r) => r.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus("Backend not reachable"));
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 Hack-Nation</h1>
        <div className={`status-badge ${status ? "status-badge--ok" : ""}`}>
          {status || "Connecting..."}
        </div>
      </header>

      <main className="app-main">
        <Chat />
      </main>
    </div>
  );
}

export default App;
