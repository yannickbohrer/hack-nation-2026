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
        features_extracted: 277,
        overall_prediction: "Likely to fail",
        confidence: 98.7,
        antibiotics: [
          { 
            name: "Ciprofloxacin", 
            prediction: "Likely to fail", 
            confidence: 99.2, 
            probability_resistant: 99, 
            genes: ["mut_gyrA_S83L", "gene_qnrS1"], 
            historical: { balanced_accuracy: 76.1, resistant_recall: 56.0, coverage: 29.1, called_accuracy: 90.7 },
            warning: "Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing."
          },
          { 
            name: "Trimethoprim/sulfamethoxazole", 
            prediction: "Likely to fail", 
            confidence: 97.8, 
            probability_resistant: 98, 
            genes: ["gene_sul2", "gene_dfrA17"],
            historical: { balanced_accuracy: 71.1, resistant_recall: 48.1, coverage: 30.5, called_accuracy: 82.7 },
            warning: "Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing."
          },
          { 
            name: "Cephalothin", 
            prediction: "Likely to work", 
            confidence: 94.5, 
            probability_resistant: 5, 
            genes: [],
            historical: { balanced_accuracy: 69.4, resistant_recall: 88.9, coverage: 92.3, called_accuracy: 83.3 },
            warning: "Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing."
          },
          { 
            name: "Nalidixic acid", 
            prediction: "No call", 
            confidence: null, 
            probability_resistant: 53, 
            genes: ["mut_gyrA_S83L"],
            historical: { balanced_accuracy: 67.6, resistant_recall: 40.0, coverage: 84.6, called_accuracy: 86.3 },
            warning: "Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing."
          }
        ],
        amr_genes_detected: ["mut_gyrA_S83L", "gene_qnrS1", "gene_sul2", "gene_dfrA17"],
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

      const antibiotics = (data.predictions || []).map(p => {
        let statusStr = "Unknown";
        if (p.prediction === "likely_to_fail") statusStr = "Likely to fail";
        else if (p.prediction === "likely_to_work") statusStr = "Likely to work";
        else if (p.prediction === "no_call") statusStr = "No call";

        const genes = p.top_supporting_features ? p.top_supporting_features.map(f => f.feature) : [];

        return {
          name: p.antibiotic.charAt(0).toUpperCase() + p.antibiotic.slice(1),
          prediction: statusStr,
          confidence: p.confidence !== null ? Math.round(p.confidence * 100 * 10) / 10 : null,
          probability_resistant: Math.round(p.probability_resistant * 100),
          genes: genes,
          warning: p.warning,
          historical: {
            balanced_accuracy: p.balanced_accuracy ? Math.round(p.balanced_accuracy * 1000) / 10 : null,
            resistant_recall: p.resistant_recall ? Math.round(p.resistant_recall * 1000) / 10 : null,
            coverage: p.coverage ? Math.round(p.coverage * 1000) / 10 : null,
            called_accuracy: p.called_accuracy ? Math.round(p.called_accuracy * 1000) / 10 : null,
          }
        };
      });

      const overall = antibiotics.some(a => a.prediction === "Likely to fail") ? "Likely to fail" : "Likely to work";
      const allGenes = new Set();
      antibiotics.forEach(ab => {
        if (ab.genes) {
          ab.genes.forEach(g => allGenes.add(g.replace(/^gene_/, "").replace(/^mut_/, "")));
        }
      });

      const amrGenes = allGenes.size > 0 ? Array.from(allGenes).slice(0, 10) : ["AMR features detected"];

      setResult({
        genome_id: data.filename || file.name,
        features_extracted: data.features_extracted || 0,
        overall_prediction: overall,
        confidence: antibiotics.length > 0 && antibiotics[0].confidence !== null ? antibiotics[0].confidence : "N/A",
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
                <div className={`status-badge-large status-${result.overall_prediction.toLowerCase().replace(/ /g, '-')}`}>
                  {result.overall_prediction}
                </div>
                
                <div className="summary-metric">
                  <span className="metric-label">Model Confidence</span>
                  <span className="metric-value">{result.confidence}{typeof result.confidence === 'number' ? '%' : ''}</span>
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

              <div className="details-panel" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div>
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
                            if (a.prediction === "Likely to work" && b.prediction !== "Likely to work") return -1;
                            if (a.prediction !== "Likely to work" && b.prediction === "Likely to work") return 1;
                            return (b.confidence || 0) - (a.confidence || 0);
                          })
                          .map(ab => {
                            const isWinner = ab.prediction === "Likely to work";
                            return (
                              <tr key={ab.name} className={isWinner ? "row-winner" : ""}>
                                <td>
                                  {isWinner && <span style={{ color: 'var(--success)', marginRight: '6px', fontWeight: '900' }}>✓</span>}
                                  {ab.name}
                                </td>
                                <td>
                                  <span className={`status-${ab.prediction.toLowerCase().replace(/ /g, '-')}`}>
                                    {ab.prediction}
                                  </span>
                                  {ab.probability_resistant !== undefined && (
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                                      Resistance prob: {ab.probability_resistant}%
                                    </div>
                                  )}
                                </td>
                                <td>{ab.confidence !== null ? `${ab.confidence}%` : "N/A"}</td>
                              </tr>
                            );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {result.antibiotics.length > 0 && result.antibiotics[0].historical && (
                  <div>
                    <h3>Historical Model Performance</h3>
                    <div className="table-wrapper">
                      <table className="amr-table">
                        <thead>
                          <tr>
                            <th>Antibiotic</th>
                            <th>Balanced Acc.</th>
                            <th>Resistant Recall</th>
                            <th>Coverage</th>
                            <th>Called Acc.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.antibiotics.map(ab => (
                            <tr key={ab.name + "-historical"}>
                              <td>{ab.name}</td>
                              <td>{ab.historical.balanced_accuracy !== null ? `${ab.historical.balanced_accuracy}%` : "-"}</td>
                              <td>{ab.historical.resistant_recall !== null ? `${ab.historical.resistant_recall}%` : "-"}</td>
                              <td>{ab.historical.coverage !== null ? `${ab.historical.coverage}%` : "-"}</td>
                              <td>{ab.historical.called_accuracy !== null ? `${ab.historical.called_accuracy}%` : "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <div>
                  <h3>Detected Resistance Features</h3>
                  <div className="gene-tags">
                    {result.amr_genes_detected.map(gene => (
                      <span key={gene} className="gene-tag">{gene}</span>
                    ))}
                  </div>
                </div>

                {result.antibiotics.length > 0 && result.antibiotics[0].warning && (
                  <div style={{ padding: '16px', backgroundColor: 'var(--bg-accent)', borderLeft: '4px solid var(--accent)', borderRadius: '4px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                    <strong>Notice:</strong> {result.antibiotics[0].warning}
                  </div>
                )}
              </div>
          </div>
