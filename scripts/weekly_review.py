#!/usr/bin/env python3
"""
Koach OS — Weekly Review Generator (CLI)
==========================================
Usage: python3 scripts/weekly_review.py

Generates weekly summary from last 7 days and prints to stdout.
For use with macOS Shortcuts or cron.
"""

import sys
from pathlib import Path
from datetime import timedelta

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_manager import (
    read_jsonl, append_jsonl, LOGS_FILE, WEEKLY_FILE, FEEDBACK_FILE,
    generate_id, timestamp_jst, now_jst, init_all_data_files,
)


def main():
    init_all_data_files()

    now = now_jst()
    week_ago = now - timedelta(days=7)
    logs = read_jsonl(LOGS_FILE)
    week_logs = [l for l in logs if l.get("timestamp", "") >= week_ago.isoformat()]

    if not week_logs:
        print("No interactions in the last 7 days.")
        return

    domain_dist = {}
    level_dist = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
    bias_freq = {}
    cp_total = 0
    routing_dist = {"claude": 0, "gpt": 0}

    for l in week_logs:
        d = l.get("domain", "unknown")
        domain_dist[d] = domain_dist.get(d, 0) + 1

        lv = l.get("intervention_level", "L1")
        level_dist[lv] = level_dist.get(lv, 0) + 1

        for b in l.get("cognitive_biases", {}).get("detected", l.get("detected_biases", [])):
            bias_freq[b] = bias_freq.get(b, 0) + 1

        if l.get("has_counterpoint") or l.get("ai_actions", {}).get("counterpoint_provided"):
            cp_total += 1

        eng = l.get("routing", {}).get("engine", "")
        if eng in routing_dist:
            routing_dist[eng] += 1

    feedback = read_jsonl(FEEDBACK_FILE)
    week_fb = [f for f in feedback if f.get("timestamp", "") >= week_ago.isoformat()]
    accepted = sum(1 for f in week_fb if f.get("response") in ("accepted", "partially_accepted"))
    acceptance_rate = round(accepted / len(week_fb) * 100) if week_fb else 0

    summary = {
        "id": generate_id("weekly"),
        "period_start": week_ago.isoformat(),
        "period_end": now.isoformat(),
        "total_interactions": len(week_logs),
        "domain_distribution": domain_dist,
        "level_distribution": level_dist,
        "bias_frequency": bias_freq,
        "counterpoint_rate_pct": round(cp_total / len(week_logs) * 100) if week_logs else 0,
        "counterpoint_acceptance_rate_pct": acceptance_rate,
        "routing_distribution": routing_dist,
        "generated_at": timestamp_jst(),
    }

    append_jsonl(WEEKLY_FILE, summary)

    # Print report
    print("=" * 50)
    print(f"📊 KOACH OS WEEKLY REVIEW")
    print(f"   {week_ago.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}")
    print("=" * 50)
    print(f"\n💬 Total interactions: {len(week_logs)}")
    print(f"\n🏷️ Domain distribution:")
    for d, c in sorted(domain_dist.items(), key=lambda x: -x[1]):
        print(f"   {d}: {c}")
    print(f"\n📊 Level distribution:")
    for lv, c in level_dist.items():
        if c > 0:
            print(f"   {lv}: {c}")
    print(f"\n⚖️ Counterpoint rate: {summary['counterpoint_rate_pct']}%")
    print(f"🔄 Acceptance rate: {acceptance_rate}%")
    print(f"\n🔀 Routing: Claude={routing_dist['claude']} GPT={routing_dist['gpt']}")
    if bias_freq:
        print(f"\n🧠 Bias detections:")
        for b, c in sorted(bias_freq.items(), key=lambda x: -x[1]):
            print(f"   {b}: {c}")
    print(f"\n✅ Summary saved to {WEEKLY_FILE}")


if __name__ == "__main__":
    main()
