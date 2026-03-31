"""
Scenario history: persists ScenarioInput + SimulationResult pairs to a JSON file.
"""
import json
import os
from datetime import datetime
from typing import List, Optional, Dict

from engine.models import ScenarioInput, SimulationResult

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "scenarios_history.json")


def _load_raw() -> List[Dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_raw(records: List[Dict]) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)


def save_scenario(scenario: ScenarioInput, result: SimulationResult) -> str:
    """Save a scenario+result to history. Returns the record id."""
    records = _load_raw()
    record_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(records)}"
    records.append({
        "id": record_id,
        "saved_at": datetime.now().isoformat(),
        "scenario": scenario.model_dump(),
        "result": result.model_dump(),
    })
    _save_raw(records)
    return record_id


def load_all() -> List[Dict]:
    """Return all history records as raw dicts (for display)."""
    return _load_raw()


def load_scenario(record_id: str) -> Optional[Dict]:
    """Return a single record by id, or None."""
    for r in _load_raw():
        if r["id"] == record_id:
            return r
    return None


def delete_scenario(record_id: str) -> bool:
    """Delete a record by id. Returns True if deleted."""
    records = _load_raw()
    new_records = [r for r in records if r["id"] != record_id]
    if len(new_records) < len(records):
        _save_raw(new_records)
        return True
    return False


def clear_history() -> None:
    """Delete all history records."""
    _save_raw([])


def get_summary_df():
    """Return a pandas DataFrame with key metrics for all history records."""
    import pandas as pd
    records = _load_raw()
    if not records:
        return pd.DataFrame()

    rows = []
    for r in records:
        s = r["scenario"]
        res = r["result"]
        rows.append({
            "ID": r["id"],
            "Date": r["saved_at"][:16],
            "Firme": res["firm_name"],
            "Période": res["period"],
            "Scénario": res["scenario_name"],
            "Modèle": s["model_name"],
            "Segment": s["segment"],
            "Gamme": s["model_range"],
            "Ventes": res["sales"],
            "CA ($)": round(res["revenue"]),
            "Profit ($)": round(res["profit"]),
            "Marge (%)": round(res["margin"] * 100, 1),
            "PDM (%)": round(res["market_share"] * 100, 2),
            "Taux service (%)": round(res["service_rate"] * 100, 1),
            "Score innov.": round(res["innovation_score"], 1),
            "Score durable": round(res["sustainability_score"], 1),
            "Valide": res["is_valid"],
        })

    return pd.DataFrame(rows)
