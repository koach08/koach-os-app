"use client";

import { DOMAIN_LABELS, DOMAIN_EMOJI, type Domain } from "@/lib/types";

interface Props {
  domain: Domain;
  onChange: (d: Domain) => void;
}

const DOMAINS: Domain[] = ["teaching", "research", "platform", "revenue", "personal", "business"];

export function DomainSelector({ domain, onChange }: Props) {
  return (
    <div className="grid grid-cols-3 gap-1.5">
      {DOMAINS.map((d) => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className="flex flex-col items-center gap-0.5 p-2 rounded-lg text-xs transition-colors"
          style={{
            background: domain === d ? "var(--color-accent)" : "var(--color-background)",
            color: domain === d ? "white" : "var(--color-text-muted)",
            border: `1px solid ${domain === d ? "var(--color-accent)" : "var(--color-border)"}`,
          }}
        >
          <span className="text-base">{DOMAIN_EMOJI[d]}</span>
          <span>{DOMAIN_LABELS[d]}</span>
        </button>
      ))}
    </div>
  );
}
