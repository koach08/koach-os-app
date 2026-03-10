"use client";

import { useState, useEffect } from "react";
import { fetchJSON } from "@/lib/api";
import { LevelBadge } from "@/components/sidebar/LevelBadge";
import type { LogEntry, Domain, Level } from "@/lib/types";

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [domain, setDomain] = useState<string>("");
  const [level, setLevel] = useState<string>("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (domain) params.set("domain", domain);
    if (level) params.set("level", level);
    if (search) params.set("search", search);
    params.set("limit", "100");

    fetchJSON<{ logs: LogEntry[] }>(`/api/logs?${params}`).then((d) =>
      setLogs(d.logs)
    ).catch(() => {});
  }, [domain, level, search]);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">Interaction Logs</h1>

        {/* Filters */}
        <div className="flex gap-3 mb-6 flex-wrap">
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          >
            <option value="">All Domains</option>
            {["teaching", "research", "platform", "revenue", "personal", "business"].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          >
            <option value="">All Levels</option>
            {["L1", "L2", "L3", "L4"].map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..."
            className="px-3 py-2 rounded-lg text-sm flex-1 min-w-[200px]"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "var(--color-text)" }}
          />
        </div>

        {/* Log entries */}
        <div className="space-y-2">
          {logs.map((log) => (
            <div
              key={log.id}
              className="p-4 rounded-xl"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
            >
              <div className="flex items-center gap-2 mb-2">
                <LevelBadge level={log.intervention_level as Level} size="sm" />
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--color-background)", color: "var(--color-text-muted)" }}>
                  {log.domain}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--color-background)", color: "var(--color-text-muted)" }}>
                  {log.routing?.engine}
                </span>
                <span className="text-xs ml-auto" style={{ color: "var(--color-text-muted)" }}>
                  {new Date(log.timestamp).toLocaleString("ja-JP")}
                </span>
              </div>
              <p className="text-sm mb-1">
                <span style={{ color: "var(--color-text-muted)" }}>User: </span>
                {log.user_input_preview}
              </p>
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                AI: {log.ai_response_preview}
              </p>
              {log.cognitive_biases?.labels?.length > 0 && (
                <div className="flex gap-1 mt-2">
                  {log.cognitive_biases.labels.map((b, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#7c3aed20", color: "#a78bfa" }}>
                      {b}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
          {logs.length === 0 && (
            <p className="text-center py-8" style={{ color: "var(--color-text-muted)" }}>No logs found</p>
          )}
        </div>
      </div>
    </div>
  );
}
