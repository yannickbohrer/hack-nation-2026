import { useState, useRef } from "react";

export default function Scanner() {
  const [file, setFile] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setResult(null);
    }
  };

  const loadMockResponse = () => {
    setResult({
        genome_id: "isolate_sample_ERR9421.fasta",
        mash_cluster: "Cluster_042",
        overall_prediction: "Resistant",
        confidence: 98.7,
        antibiotics: [
          { name: "Ciprofloxacin", prediction: "Resistant", confidence: 99.2 },
          { name: "Ceftriaxone", prediction: "Resistant", confidence: 97.8 },
          { name: "Meropenem", prediction: "Resistant", confidence: 94.5 },
          { name: "Gentamicin", prediction: "Susceptible", confidence: 88.3 },
          { name: "Azithromycin", prediction: "Susceptible", confidence: 92.1 }
        ],
        amr_genes_detected: ["blaNDM-1", "blaCTX-M-15", "qnrS1", "tet(A)", "sul2"],
        processing_time: "1.18s"
    });
  };

  const handleScan = async () => {
    if (!file) return;
    setIsScanning(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/predict/fasta`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();

      const antibiotics = Object.keys(data.predictions || {}).map(name => {
        const p = data.predictions[name];
        if (p.error) {
          return { name, prediction: "Error", confidence: 0, genes: [] };
        }
        let statusStr = "Unknown";
        if (p.prediction === "resistant") statusStr = "Resistant";
        else if (p.prediction === "susceptible") statusStr = "Susceptible";
        else if (p.prediction === "uncertain (no-call)") statusStr = "Uncertain";

        return {
          name,
          prediction: statusStr,
          confidence: Math.round((p.confidence_score || 0) * 100 * 10) / 10,
          genes: p.top_contributing_features ? p.top_contributing_features.map(f => f.feature) : []
        };
      });

      const overall = antibiotics.some(a => a.prediction === "Resistant") ? "Resistant" : "Susceptible";
      const allGenes = new Set();
      antibiotics.forEach(ab => {
        if (ab.genes) {
          ab.genes.forEach(g => allGenes.add(g.replace(/^gene_/, "")));
        }
      });

      // fallback to mock genes if none found but features were extracted
      const amrGenes = allGenes.size > 0 ? Array.from(allGenes).slice(0, 10) : ["AMR features detected"];

      setResult({
        genome_id: data.filename || file.name,
        features_extracted: data.features_extracted || 0,
        overall_prediction: overall,
        confidence: antibiotics.length > 0 ? antibiotics[0].confidence : 0,
        antibiotics: antibiotics,
        amr_genes_detected: amrGenes,
        processing_time: "< 5s"
      });
    } catch (error) {
      console.error("Scan error:", error);
      alert("Failed to analyze sequence: " + error.message);
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <div className="scanner-container">
      {!result ? (
        <div className="upload-section">
          <div 
            className="upload-dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              accept=".fasta,.fna,.fa" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              style={{ display: "none" }} 
            />
            <div className="upload-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <h3>{file ? file.name : "Upload FASTA sequence"}</h3>
            <p>{file ? "Ready to analyze" : "Drag and drop your genome file here, or click to browse"}</p>
          </div>

          <div style={{ display: "flex", gap: "12px", width: "100%" }}>
            <button 
              className={`scan-btn ${isScanning ? "scanning" : ""}`} 
              onClick={handleScan}
              disabled={!file || isScanning}
              style={{ flex: 2 }}
            >
              {isScanning ? (
                <span className="scanning-text">
                  <span className="spinner"></span> Analyzing sequence...
                </span>
              ) : "Initiate Scan"}
            </button>

            <button 
              className="scan-btn scan-mock-btn" 
              onClick={loadMockResponse}
              disabled={isScanning}
              title="Load a comprehensive sample report"
              style={{ flex: 1 }}
            >
              View Sample Report
            </button>
          </div>
        </div>
      ) : (
        <div className="result-section">
          <div className="result-header">
            <div>
              <h2 style={{ fontSize: "1.75rem", fontWeight: "700", marginBottom: "8px" }}>Comprehensive Analysis Report</h2>
              <p style={{ fontSize: "1rem", color: "var(--text-muted)" }}>
                Genome File: <span style={{ fontWeight: "600", color: "var(--text-main)" }}>{result.genome_id}</span>
              </p>
            </div>
            <button className="reset-btn" onClick={() => { setFile(null); setResult(null); }}>
              New Analysis
            </button>
          </div>
          
          <div className="result-grid">
              <div className="summary-panel">
                <h3>Overall Risk Profile</h3>
                <div className={`status-badge-large status-${result.overall_prediction.toLowerCase()}`}>
                  {result.overall_prediction}
                </div>
                
                <div className="summary-metric">
                  <span className="metric-label">Model Confidence</span>
                  <span className="metric-value">{result.confidence}%</span>
                </div>
                <div className="summary-metric">
                  <span className="metric-label">Features Extracted</span>
                  <span className="metric-value">{result.features_extracted}</span>
                </div>
                <div className="summary-metric">
                  <span className="metric-label">Processing Time</span>
                  <span className="metric-value">{result.processing_time}</span>
                </div>
              </div>

              <div className="details-panel">
                <h3>Antimicrobial Susceptibility Testing</h3>
                <div className="table-wrapper">
                  <table className="amr-table">
                    <thead>
                      <tr>
                        <th>Antibiotic</th>
                        <th>Prediction</th>
                        <th>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...result.antibiotics]
                        .sort((a, b) => {
                          if (a.prediction === "Susceptible" && b.prediction !== "Susceptible") return -1;
                          if (a.prediction !== "Susceptible" && b.prediction === "Susceptible") return 1;
                          return b.confidence - a.confidence;
                        })
                        .map(ab => {
                          const isWinner = ab.prediction === "Susceptible";
                          return (
                            <tr key={ab.name} className={isWinner ? "row-winner" : ""}>
                              <td>
                                {isWinner && <span style={{ color: 'var(--success)', marginRight: '6px', fontWeight: '900' }}>✓</span>}
                                {ab.name}
                              </td>
                              <td>
                                <span className={`status-${ab.prediction.toLowerCase()}`}>
                                  {ab.prediction}
                                </span>
                              </td>
                              <td>{ab.confidence}%</td>
                            </tr>
                          );
                      })}
                    </tbody>
                  </table>
                </div>

                <h3 style={{ marginTop: '24px' }}>Detected Resistance Genes</h3>
                <div className="gene-tags">
                  {result.amr_genes_detected.map(gene => (
                    <span key={gene} className="gene-tag">{gene}</span>
                  ))}
                </div>
              </div>
          </div>
        </div>
      )}
    </div>
  );
}
