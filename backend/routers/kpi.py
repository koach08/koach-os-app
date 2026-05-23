"""
KPI ミニダッシュ。
data/kpi.json をユーザー側 (Cron / 手動 / 外部スクリプト) が更新する前提。
読むだけのシンプル API。

スキーマ例:
{
  "updated_at": "2026-05-23T20:00:00+09:00",
  "metrics": [
    {"id": "egaku_users", "label": "EGAKU 登録者", "value": 149, "unit": "人", "delta_7d": 12, "url": "..."},
    {"id": "egaku_mrr", "label": "EGAKU MRR", "value": 0, "unit": "円"},
    {"id": "crypto_balance", "label": "crypto-trader 残高", "value": 198000, "unit": "円", "delta_7d": -3200},
    {"id": "investment_total", "label": "総資産", "value": 5200000, "unit": "円"},
    {"id": "gumroad_sales", "label": "Gumroad 売上 (月)", "value": 0, "unit": "円"}
  ]
}
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import DATA_DIR, now_jst, timestamp_jst

router = APIRouter()

KPI_FILE = DATA_DIR / "kpi.json"


class Metric(BaseModel):
    id: str
    label: str
    value: float | int
    unit: str = ""
    delta_7d: float | int | None = None
    url: str = ""
    category: str = ""  # "growth" | "revenue" | "capital" | "health" | "other"


class KpiSnapshot(BaseModel):
    metrics: list[Metric]


def _read() -> dict:
    if not KPI_FILE.exists():
        return {"updated_at": None, "metrics": []}
    try:
        return json.loads(KPI_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": None, "metrics": []}


def _write(data: dict):
    KPI_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/kpi")
def get_kpi():
    data = _read()
    metrics = data.get("metrics", [])
    by_category: dict[str, list] = {}
    for m in metrics:
        cat = m.get("category", "other")
        by_category.setdefault(cat, []).append(m)
    return {
        "updated_at": data.get("updated_at"),
        "metrics": metrics,
        "by_category": by_category,
        "now": now_jst().isoformat(),
    }


@router.post("/kpi")
def post_kpi(payload: KpiSnapshot):
    data = {
        "updated_at": timestamp_jst(),
        "metrics": [m.model_dump() for m in payload.metrics],
    }
    _write(data)
    return data


class MetricPatch(BaseModel):
    id: str
    label: str | None = None
    value: float | int | None = None
    unit: str | None = None
    delta_7d: float | int | None = None
    url: str | None = None
    category: str | None = None


@router.patch("/kpi/metric")
def patch_metric(p: MetricPatch):
    data = _read()
    metrics = data.get("metrics", [])
    found = None
    for m in metrics:
        if m.get("id") == p.id:
            found = m
            break
    if not found:
        # 新規追加
        found = {"id": p.id, "label": p.label or p.id, "value": p.value or 0, "unit": p.unit or "", "category": p.category or "other"}
        metrics.append(found)
    else:
        if p.label is not None:
            found["label"] = p.label
        if p.value is not None:
            found["value"] = p.value
        if p.unit is not None:
            found["unit"] = p.unit
        if p.delta_7d is not None:
            found["delta_7d"] = p.delta_7d
        if p.url is not None:
            found["url"] = p.url
        if p.category is not None:
            found["category"] = p.category
    data["metrics"] = metrics
    data["updated_at"] = timestamp_jst()
    _write(data)
    return found


@router.delete("/kpi/metric/{metric_id}")
def delete_metric(metric_id: str):
    data = _read()
    data["metrics"] = [m for m in data.get("metrics", []) if m.get("id") != metric_id]
    data["updated_at"] = timestamp_jst()
    _write(data)
    return {"ok": True}
