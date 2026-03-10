#!/usr/bin/env python3
"""
Koach OS — Quick Interaction Log (CLI)
========================================
Usage: python3 scripts/quick_log.py --domain teaching --input "今日の授業でXを試した"

For use with macOS Shortcuts or command line.
"""

import argparse
import sys
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_manager import append_jsonl, LOGS_FILE, generate_id, timestamp_jst, now_jst, init_all_data_files


def main():
    parser = argparse.ArgumentParser(description="Quick log an interaction to Koach OS")
    parser.add_argument("--domain", choices=["teaching", "research", "platform", "revenue", "personal", "business"],
                        default="personal", help="Domain of the interaction")
    parser.add_argument("--input", "-i", required=True, help="What happened / user input text")
    parser.add_argument("--level", choices=["L1", "L2", "L3", "L4"], default="L1",
                        help="Intervention level (default: L1)")
    args = parser.parse_args()

    init_all_data_files()

    t = now_jst()
    hour = t.hour
    if hour < 12:
        tod = "morning"
    elif hour < 18:
        tod = "afternoon"
    else:
        tod = "evening"

    entry = {
        "id": generate_id("log"),
        "timestamp": timestamp_jst(),
        "domain": args.domain,
        "task_type": "quick_log",
        "intervention_level": args.level,
        "level_auto_detected": False,
        "detection_axes": {
            "public_exposure": False, "long_term_impact": False,
            "emotional_signals": False, "value_conflict": False,
        },
        "routing": {"engine": "manual", "model": "none", "reason": "cli_quick_log"},
        "cognitive_biases": {"detected": [], "corrections_applied": []},
        "acceptance_gradient_used": "none",
        "signals": {
            "language": "japanese" if any(ord(c) > 0x3000 for c in args.input) else "english",
            "input_length": len(args.input),
            "time_of_day": tod,
        },
        "ai_actions": {
            "counterpoint_provided": False, "bias_check_provided": False,
            "risk_assessment_provided": False, "five_year_check": False,
        },
        "user_input": args.input,
        "ai_response_length": 0,
        "has_counterpoint": False,
        "has_bias_check": False,
    }

    append_jsonl(LOGS_FILE, entry)
    print(f"✅ Logged: [{args.domain}] {args.input[:60]}...")


if __name__ == "__main__":
    main()
