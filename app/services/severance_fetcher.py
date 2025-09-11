#!/usr/bin/env python3
"""
Severance Cap Fetcher - Real API integration with unit detection and normalization
"""
import requests
import json
import re
import os
import csv
import uuid
import datetime
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List

logger = logging.getLogger("severance_fetcher")
os.makedirs("/tmp/data_snapshots", exist_ok=True)

def save_raw(bytes_or_text, prefix="api_raw", ext="bin"):
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fn = f"/tmp/data_snapshots/{prefix}_{ts}.{ext}"
    mode = "wb" if isinstance(bytes_or_text, (bytes, bytearray)) else "w"
    with open(fn, mode, encoding="utf-8" if mode=="w" else None) as f:
        if mode == "wb":
            f.write(bytes_or_text)
        else:
            f.write(bytes_or_text)
    return fn

def clean_number_token(s):
    s = str(s).strip()
    s = re.sub(r"[^\d\-,\.]", "", s)
    if s.count(",") and s.count("."):
        s = s.replace(",", "")
    else:
        s = s.replace(",", "")
    if s in ("", "-", "."):
        raise ValueError("Empty after cleanup")
    return float(s)

def decide_unit_and_normalize(num):
    if num >= 100000:
        return {"unit":"annual","annual":float(num),"monthly":round(num/12.0,2)}
    if 1000 <= num < 100000:
        return {"unit":"monthly","monthly":float(num),"annual":round(num*12.0,2)}
    # small number - assume monthly but flag
    return {"unit":"monthly_low_confidence","monthly":float(num),"annual":round(num*12.0,2)}

def discover_candidates(obj, prefix=""):
    out=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v,(int,float)):
                out.append((path,v))
            elif isinstance(v,str) and re.search(r"\d", v):
                try:
                    _ = clean_number_token(v)
                    out.append((path,v))
                except:
                    pass
            elif isinstance(v, dict):
                out += discover_candidates(v, path)
            elif isinstance(v, list):
                for i, it in enumerate(v):
                    out += discover_candidates(it, f"{path}[{i}]")
    return out

def fetch_and_normalize_severance(url, params=None, headers=None, prefer_keys=None, persist_csv="/tmp/severance_caps.csv"):
    """
    Fetch severance cap from API with unit detection and normalization
    """
    r = requests.get(url, params=params or {}, headers=headers or {}, timeout=30)
    r.raise_for_status()
    raw_bytes = r.content
    raw_path = save_raw(raw_bytes, prefix="severance_raw", ext="bin")
    
    # try json
    try:
        j = r.json()
    except Exception:
        text = r.text
        save_raw(text, prefix="severance_text", ext="txt")
        raise RuntimeError("Non JSON response; raw saved to " + raw_path)
    
    # save pretty json
    save_raw(json.dumps(j, ensure_ascii=False, indent=2), prefix="severance_json", ext="json")
    
    # choose candidate
    candidate = None
    source_key = None
    if prefer_keys:
        for k in prefer_keys:
            # try deep lookup simple dotted keys
            parts = k.split(".")
            cur = j
            ok=True
            for p in parts:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok=False; break
            if ok and cur not in (None,""):
                candidate = cur; source_key = k; break
    
    if candidate is None:
        cand_list = discover_candidates(j)
        if not cand_list:
            raise RuntimeError(f"No numeric candidates found in JSON; raw saved {raw_path}")
        source_key, candidate = cand_list[0]
    
    try:
        parsed = clean_number_token(candidate)
    except Exception as e:
        raise RuntimeError(f"Failed parse candidate '{candidate}': {e}")
    
    norm = decide_unit_and_normalize(parsed)
    trace = str(uuid.uuid4())
    
    row = {
        "trace_id": trace,
        "source_url": r.url,
        "source_key": source_key,
        "raw_value_text": str(candidate),
        "parsed_value": parsed,
        "unit_inferred": norm["unit"],
        "monthly": norm.get("monthly"),
        "annual": norm.get("annual"),
        "raw_snapshot_path": raw_path,
        "fetched_at": datetime.datetime.utcnow().isoformat()
    }
    
    # persist csv append
    write_header = not os.path.exists(persist_csv)
    with open(persist_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header: w.writeheader()
        w.writerow(row)
    
    logger.info("Fetched severance cap: %s", row)
    return row

def get_current_severance_cap_real():
    """
    Get current severance cap using real API with fallback
    """
    try:
        # Try to fetch from our tax data API
        url = "http://localhost:8000/api/v1/tax-data/severance-cap"
        row = fetch_and_normalize_severance(
            url, 
            prefer_keys=["monthly_cap", "severance_cap", "cap"]
        )
        return {
            "monthly": Decimal(str(row["monthly"])),
            "annual": Decimal(str(row["annual"])),
            "source": "real_api",
            "trace_id": row["trace_id"]
        }
    except Exception as e:
        logger.warning(f"Failed to fetch from real API: {e}")
        # Fallback to known values
        return {
            "monthly": Decimal("41667"),
            "annual": Decimal("500004"),
            "source": "fallback",
            "trace_id": str(uuid.uuid4())
        }
