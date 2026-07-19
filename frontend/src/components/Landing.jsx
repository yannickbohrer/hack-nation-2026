export default function Landing({ onStart }) {
  return (
    <div className="page-container">
      <header className="landing-header">
        <p className="landing-tagline">The Clinical Bottleneck</p>
        <h1 className="landing-title">Eliminating the 72-hour wait for targeted antibiotics.</h1>
        <p className="landing-desc">
          When a patient presents with a severe infection, time is the most critical variable. Today, even after rapid genomic sequencing, determining the correct antibiotic requires physically culturing the pathogen alongside drugs to observe resistance—a process that adds <strong>24 to 72 hours</strong> to the diagnostic timeline. Genome Firewall replaces this phenotypic bottleneck with instantaneous, calibrated computational predictions.
        </p>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="scan-btn" style={{ width: 'auto', padding: '12px 24px' }} onClick={onStart}>
            Upload a FASTA →
          </button>
        </div>
      </header>

      <h2 className="landing-tagline" style={{ marginBottom: "24px", color: "var(--text-main)", textAlign: "center", fontSize: "0.85rem" }}>The Diagnostic Flow</h2>
      
      <div className="flowchart-container" style={{ 
        background: "var(--surface)", 
        border: "1px solid var(--border)", 
        borderRadius: "var(--radius-md)", 
        padding: "48px 24px", 
        marginBottom: "48px",
        boxShadow: "var(--shadow-sm)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center"
      }}>
        
        {/* Step 1 */}
        <div style={{ 
          background: "#fff", border: "1px solid var(--border)", borderRadius: "99px", 
          padding: "12px 24px", display: "flex", alignItems: "center", gap: "12px",
          boxShadow: "0 2px 4px rgba(0,0,0,0.02)", zIndex: 2
        }}>
          <div style={{ fontSize: "1.2rem" }}>🩺</div>
          <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.95rem" }}>1. Patient Sample Collected</div>
        </div>

        {/* Down Arrow */}
        <div style={{ height: "30px", borderLeft: "2px solid var(--border)", width: "0" }}></div>

        {/* Step 2 */}
        <div style={{ 
          background: "#fff", border: "1px solid var(--border)", borderRadius: "99px", 
          padding: "12px 24px", display: "flex", alignItems: "center", gap: "12px",
          boxShadow: "0 2px 4px rgba(0,0,0,0.02)", zIndex: 2
        }}>
          <div style={{ fontSize: "1.2rem" }}>🧬</div>
          <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.95rem" }}>2. Pathogen DNA Sequenced</div>
        </div>

        {/* Vertical Drop */}
        <div style={{ width: "2px", height: "16px", background: "var(--border)" }}></div>
        
        {/* Horizontal Split + Vertical Drops */}
        <div style={{ display: "flex", width: "100%", maxWidth: "344px", height: "24px", marginBottom: "8px" }}>
          <div style={{ flex: 1, borderTop: "2px dashed var(--border)", borderLeft: "2px dashed var(--border)", borderTopLeftRadius: "8px" }}></div>
          <div style={{ flex: 1, borderTop: "2px solid var(--primary)", borderRight: "2px solid var(--primary)", borderTopRightRadius: "8px" }}></div>
        </div>

        {/* Split Branches */}
        <div style={{ display: "flex", gap: "24px", width: "100%", maxWidth: "700px", justifyContent: "center" }}>
          
          {/* Path A */}
          <div style={{ 
            flex: 1, border: "1px dashed #ef4444", borderRadius: "12px", padding: "24px",
            display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
            background: "#fff"
          }}>
            <div style={{ fontSize: "0.7rem", fontWeight: "700", color: "#ef4444", letterSpacing: "0.05em", marginBottom: "16px" }}>STATUS QUO</div>
            <div style={{ fontSize: "2rem", marginBottom: "12px" }}>🧫</div>
            <div style={{ fontWeight: "600", color: "var(--text-main)", marginBottom: "8px" }}>3a. Physical Culturing</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.5, marginBottom: "24px" }}>
              Lab physically grows the bacteria with antibiotics to observe resistance.
            </div>
            <div style={{ 
              background: "#fef2f2", color: "#dc2626", fontWeight: "700", 
              padding: "8px 12px", borderRadius: "6px", fontSize: "0.85rem",
              marginTop: "auto", width: "100%", border: "1px solid rgba(220, 38, 38, 0.2)"
            }}>
              ⏳ 24 - 72 Hours
            </div>
          </div>

          {/* Path B */}
          <div style={{ 
            flex: 1, border: "2px solid var(--primary)", borderRadius: "12px", padding: "24px",
            display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
            background: "rgba(2, 132, 199, 0.02)", boxShadow: "0 4px 12px rgba(2, 132, 199, 0.05)"
          }}>
            <div style={{ fontSize: "0.7rem", fontWeight: "700", color: "var(--primary)", letterSpacing: "0.05em", marginBottom: "16px" }}>OUR VISION</div>
            <div style={{ fontSize: "2rem", marginBottom: "12px" }}>⚡</div>
            <div style={{ fontWeight: "600", color: "var(--text-main)", marginBottom: "8px" }}>3b. In-Silico Prediction</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.5, marginBottom: "24px" }}>
              Genome Firewall instantly detects AMR genes and runs ML models on the FASTA.
            </div>
            <div style={{ 
              background: "var(--primary)", color: "#fff", fontWeight: "700", 
              padding: "8px 12px", borderRadius: "6px", fontSize: "0.85rem",
              marginTop: "auto", width: "100%",
              boxShadow: "0 2px 8px rgba(2, 132, 199, 0.3)"
            }}>
              🚀 &lt; 1 Min
            </div>
          </div>

        </div>
      </div>

      <section className="stats-grid">
        <div>
          <div className="stat-val">3 Days</div>
          <div className="stat-label">Current delay eliminated</div>
        </div>
        <div>
          <div className="stat-val">&lt; 1 Min</div>
          <div className="stat-label">Time to prediction</div>
        </div>
        <div>
          <div className="stat-val">100%</div>
          <div className="stat-label">In-silico approach</div>
        </div>
        <div>
          <div className="stat-val">1 FASTA</div>
          <div className="stat-label">Required input</div>
        </div>
      </section>
    </div>
  );
}
