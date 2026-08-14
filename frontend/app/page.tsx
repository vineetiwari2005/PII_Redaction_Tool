"use client";

import { useState, useRef, useCallback, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EntityPreview {
  original: string;
  replacement: string;
  type: string;
}

interface RedactionResult {
  task_id: string;
  stats: {
    total_entities: number;
    unique_entities: number;
    by_type: Record<string, number>;
    definitions_extracted: number;
    segments_processed: number;
  };
  downloads: {
    redacted: string;
    entity_map: string;
  };
  preview: EntityPreview[];
}

type Phase = "idle" | "processing" | "done" | "error";

// ---------------------------------------------------------------------------
// API URL
// ---------------------------------------------------------------------------

function resolveApi(): string {
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, "");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  if (typeof window !== "undefined" && (window as any).__API_URL__)
    return String((window as any).__API_URL__).replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location.port === "3000")
    return "http://localhost:8000";
  return "";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [hovering, setHovering] = useState(false);
  const [result, setResult] = useState<RedactionResult | null>(null);
  const [errMsg, setErrMsg] = useState("");
  const [api, setApi] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const url = resolveApi();
    setApi(url);
    if (url) console.log(`[PII Tool] Backend: ${url}`);
    else console.warn("[PII Tool] No backend URL configured");
  }, []);

  const pickFile = useCallback((f: File) => {
    if (!f.name.toLowerCase().endsWith(".docx")) {
      setErrMsg("Only .docx files are supported.");
      return;
    }
    setFile(f);
    setErrMsg("");
    setResult(null);
    setPhase("idle");
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setHovering(false);
      if (e.dataTransfer.files.length > 0) pickFile(e.dataTransfer.files[0]);
    },
    [pickFile]
  );

  const submit = async () => {
    if (!file) return;
    setPhase("processing");
    setErrMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${api}/api/redact`, { method: "POST", body: fd });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as Record<string, string>).detail || `Error ${res.status}`);
      }
      const data: RedactionResult = await res.json();
      setResult(data);
      setPhase("done");
    } catch (err: unknown) {
      setErrMsg(err instanceof Error ? err.message : "Something went wrong");
      setPhase("error");
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setPhase("idle");
    setErrMsg("");
  };

  return (
    <main className="flex-1 flex flex-col items-center px-4 py-10 sm:py-16">
      {/* Header */}
      <header className="text-center mb-8 appear">
        <div className="flex items-center justify-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center text-white text-lg shadow-md">
            🔒
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
            PII Redaction Tool
          </h1>
        </div>
        <p className="text-slate-500 max-w-md mx-auto text-sm sm:text-base">
          Upload a Word document to automatically detect and redact sensitive
          information using AI-powered analysis.
        </p>
      </header>

      {/* Main card */}
      <div className="card w-full max-w-xl p-6 sm:p-8 appear" style={{ animationDelay: "0.1s" }}>
        {/* Drop zone */}
        <div
          className={`drop-area p-8 sm:p-10 text-center mb-6 ${hovering ? "active" : ""}`}
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setHovering(true); }}
          onDragLeave={() => setHovering(false)}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".docx"
            className="hidden"
            onChange={(e) => { if (e.target.files?.[0]) pickFile(e.target.files[0]); }}
          />
          {file ? (
            <div>
              <div className="text-3xl mb-1">📄</div>
              <p className="text-slate-800 font-medium">{file.name}</p>
              <p className="text-slate-400 text-sm mt-1">
                {(file.size / 1024 / 1024).toFixed(1)} MB — Click to change
              </p>
            </div>
          ) : (
            <div>
              <div className="text-3xl mb-1">📤</div>
              <p className="text-slate-600 font-medium">Drop your .docx here</p>
              <p className="text-slate-400 text-sm mt-1">or click to browse</p>
            </div>
          )}
        </div>

        {/* Submit */}
        <button className="btn w-full" disabled={!file || phase === "processing"} onClick={submit}>
          {phase === "processing" ? (
            <span className="flex items-center justify-center gap-2">
              <span className="spin" />
              Analyzing document…
            </span>
          ) : (
            "Redact Document"
          )}
        </button>

        {/* Progress */}
        {phase === "processing" && (
          <div className="mt-4 appear">
            <div className="progress-track running"><div className="progress-fill" /></div>
            <p className="text-slate-400 text-xs mt-2 text-center">
              Running spaCy NER + Presidio analysis… This may take 30–60 seconds.
            </p>
          </div>
        )}

        {/* Error */}
        {errMsg && (
          <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm appear">
            ⚠ {errMsg}
          </div>
        )}
      </div>

      {/* Results */}
      {phase === "done" && result && (
        <div className="w-full max-w-xl mt-6 space-y-4 appear" style={{ animationDelay: "0.1s" }}>
          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="metric">
              <div className="metric-value">{result.stats.total_entities}</div>
              <div className="metric-label">Total Redacted</div>
            </div>
            <div className="metric">
              <div className="metric-value">{result.stats.unique_entities}</div>
              <div className="metric-label">Unique Entities</div>
            </div>
            <div className="metric">
              <div className="metric-value">{result.stats.segments_processed.toLocaleString()}</div>
              <div className="metric-label">Segments</div>
            </div>
            <div className="metric">
              <div className="metric-value">{result.stats.definitions_extracted}</div>
              <div className="metric-label">Glossary Terms</div>
            </div>
          </div>

          {/* Type breakdown */}
          <div className="card p-5">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Detected Entity Types
            </h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(result.stats.by_type)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <span key={type} className={`tag ${type}`}>
                    {type.replace("_", " ")}: {count}
                  </span>
                ))}
            </div>
          </div>

          {/* Downloads */}
          <div className="card p-5">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Downloads
            </h3>
            <div className="flex flex-wrap gap-3">
              <a href={`${api}${result.downloads.redacted}`} className="download-link" download>
                📥 Redacted Document
              </a>
              <a href={`${api}${result.downloads.entity_map}`} className="download-link" download>
                📋 Entity Map (JSON)
              </a>
            </div>
          </div>

          {/* Preview table */}
          {result.preview.length > 0 && (
            <div className="card p-5 overflow-x-auto">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Entity Map Preview
              </h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Original</th>
                    <th>Replacement</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {result.preview.map((e, i) => (
                    <tr key={i}>
                      <td className="font-mono text-xs">{e.original}</td>
                      <td className="font-mono text-xs">{e.replacement}</td>
                      <td><span className={`tag ${e.type}`}>{e.type}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.preview.length >= 20 && (
                <p className="text-slate-400 text-xs mt-2 text-center">
                  Showing first 20 entries. Full map in JSON download.
                </p>
              )}
            </div>
          )}

          {/* Reset */}
          <button
            className="w-full py-3 rounded-xl border border-slate-200 text-slate-400 hover:text-slate-600 hover:border-slate-300 transition-all text-sm cursor-pointer"
            onClick={reset}
          >
            ↩ Process another document
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-auto pt-12 pb-6 text-center text-slate-400 text-xs">
        <p>
          Powered by <span className="text-slate-600">spaCy</span> +{" "}
          <span className="text-slate-600">Microsoft Presidio</span>
        </p>
        <p className="mt-1">PII Redaction Tool — Scalar Assignment</p>
      </footer>
    </main>
  );
}
