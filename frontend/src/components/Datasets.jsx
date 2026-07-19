const mockDatasets = [
  { id: 1, name: "BV-BRC Public", source: "BV-BRC", isolates: 45000, updated: "2024-03" },
  { id: 2, name: "NCBI Pathogen Detection", source: "NCBI", isolates: 120000, updated: "2024-04" },
  { id: 3, name: "Clinical Validation Cohort", source: "Internal", isolates: 3011, updated: "2024-05" }
];

const mockModels = [
  { id: 1, name: "Mash + XGBoost Ensemble", version: "v1.2", approach: "K-mer distance clustering and gradient boosting on AMRFinderPlus features.", training: 3011, calibration: "Isotonic Regression" },
  { id: 2, name: "Molecular Target Gate", version: "v0.9", approach: "Rule-based filtering ensuring detected genes match the expected drug target class.", training: 0, calibration: "Deterministic" }
];

export default function Datasets() {
  return (
    <div className="page-container">
      <header className="landing-header">
        <p className="landing-tagline">Documentation</p>
        <h1 className="landing-title">Supported datasets & models</h1>
        <p className="landing-desc">
          Genome Firewall is trained and evaluated on openly available bacterial genome data linked to laboratory-measured susceptibility results. AMR features are extracted with AMRFinderPlus (default) and cross-referenced with ResFinder. Every reference is pinned per job so results stay reproducible.
        </p>
      </header>

      <section>
        <h2 className="landing-tagline" style={{ marginBottom: "16px", color: "var(--text-main)" }}>Reference datasets</h2>
        <div className="dataset-table">
          <div className="dataset-row dataset-header-row">
            <div>Dataset</div>
            <div>Source</div>
            <div>Isolates</div>
            <div>Updated</div>
          </div>
          {mockDatasets.map(d => (
            <div key={d.id} className="dataset-row">
              <div className="dataset-name">{d.name}</div>
              <div>{d.source}</div>
              <div style={{ fontFamily: "monospace" }}>{d.isolates.toLocaleString()}</div>
              <div style={{ fontFamily: "monospace" }}>{d.updated}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="landing-tagline" style={{ marginBottom: "16px", color: "var(--text-main)" }}>Prediction models</h2>
        <div className="landing-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          {mockModels.map(m => (
            <div key={m.id} className="info-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "12px" }}>
                <div className="info-card-title" style={{ marginBottom: 0 }}>{m.name}</div>
                <div className="info-card-tag" style={{ marginBottom: 0, color: "var(--text-muted)" }}>{m.version}</div>
              </div>
              <div className="info-card-body" style={{ marginBottom: "20px" }}>{m.approach}</div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", borderTop: "1px solid var(--border-light)", paddingTop: "12px" }}>
                <span style={{ textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>Training</span>
                <span style={{ fontFamily: "monospace", fontWeight: 600 }}>{m.training > 0 ? `${m.training.toLocaleString()} isolates` : "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginTop: "8px" }}>
                <span style={{ textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>Calibration</span>
                <span style={{ fontWeight: 500 }}>{m.calibration}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
