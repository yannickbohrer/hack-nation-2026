import { useState } from "react";
import Scanner from "./components/Scanner";
import Landing from "./components/Landing";
import Datasets from "./components/Datasets";

function App() {
  const [currentPage, setCurrentPage] = useState("landing");

  return (
    <div className="app">
      <header className="app-header">
        <h1 onClick={() => setCurrentPage("landing")} style={{ cursor: "pointer" }}>
          <img src="/superbugs.webp" alt="Genome Firewall Logo" className="app-logo" />
          Genome Firewall
        </h1>
        <nav className="main-nav">
          <button className={`nav-link ${currentPage === "landing" ? "active" : ""}`} onClick={() => setCurrentPage("landing")}>Vision 🚀</button>
          <button className={`nav-link ${currentPage === "datasets" ? "active" : ""}`} onClick={() => setCurrentPage("datasets")}>Datasets</button>
          <button className={`nav-link scan-nav-btn ${currentPage === "scanner" ? "active" : ""}`} onClick={() => setCurrentPage("scanner")}>Upload FASTA</button>
        </nav>
      </header>

      <main className="app-main">
        {currentPage === "landing" && <Landing onStart={() => setCurrentPage("scanner")} />}
        {currentPage === "scanner" && <Scanner />}
        {currentPage === "datasets" && <Datasets />}
      </main>
    </div>
  );
}

export default App;
