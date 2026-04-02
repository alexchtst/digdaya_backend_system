import math
import statistics
from typing import Optional

STATUTORY_TAX_RATE = 0.22
BI_RATE            = 0.0575
DE_SAFE_HARBOR     = 4.0
RP_HAVEN_THRESHOLD = 0.50
ETR_GAP_THRESHOLD  = 0.10

SCORE_WEIGHTS = {
    "etr":       0.25,
    "margin":    0.20,
    "rp_haven":  0.20,
    "debt":      0.15,
    "ownership": 0.10,
    "conduct":   0.10,
}

RISK_TIERS = [
    (81, 100, "critical", "escalate to formal audit"),
    (61,  80, "high",     "recommend screening"),
    (31,  60, "medium",   "watchlist"),
    ( 0,  30, "low",      "no action"),
]

TAX_HAVEN_JURISDICTIONS = {
    "VGB", "CYM", "BMU", "BVI",
    "SGP", "NLD", "IRL", "LUX", "MLT",
    "CHE", "LIE", "MCO",
    "MUS", "SYC", "MDV",
    "PAN", "BHS", "ATG",
}

def _safe(record, key, default=None):
    val = record.get(key, default)
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _safe_pos(record, key):
    val = _safe(record, key)
    return val if (val is not None and val > 0) else None


def _zscore(value, mean, std):
    if std == 0:
        return None
    return (value - mean) / std


def _z_to_pts(z: Optional[float]):
    if z is None:
        return 0.0
    return min(100.0, max(0.0, abs(z) * 20.0))


def _persistence_multiplier(score, consecutive_years):
    if consecutive_years >= 3:
        return min(100.0, score * 1.3)
    return score


def _get_risk_tier(score) -> dict:
    for low, high, label, action in RISK_TIERS:
        if low <= score <= high:
            return {"tier": label, "action": action, "score_range": f"{low}–{high}"}
    return {"tier": "low", "action": "no action", "score_range": "0–30"}


def compute_etr(record):
    beban  = _safe_pos(record, "beban_pajak")
    if beban is None:
        return None

    denom = _safe_pos(record, "laba_sebelum_pajak") or _safe_pos(record, "revenue")
    if denom is None:
        return None

    etr = beban / denom
    return None if etr > 2.0 else round(etr, 6)


def compute_etr_score(record, all_records: list) -> dict:
    etr = compute_etr(record)
    if etr is None:
        return {
            "score": 0.0, "etr": None, "etr_gap": None,
            "z_score": None, "flag": False,
            "flag_reason": None, "note": "data_tidak_tersedia",
        }

    etr_gap = STATUTORY_TAX_RATE - etr

    all_gaps = []
    for r in all_records:
        e = compute_etr(r)
        if e is not None:
            all_gaps.append(STATUTORY_TAX_RATE - e)

    score = 0.0
    z = None
    if len(all_gaps) >= 3:
        mean_g = statistics.mean(all_gaps)
        std_g  = statistics.stdev(all_gaps) if len(all_gaps) > 1 else 0
        z      = _zscore(etr_gap, mean_g, std_g)
        score  = _z_to_pts(z) if (z is not None and z > 0) else 0.0
    elif etr_gap > ETR_GAP_THRESHOLD:
        score = min(100.0, (etr_gap / ETR_GAP_THRESHOLD) * 40.0)

    flag = etr_gap > ETR_GAP_THRESHOLD
    mode = "laba_sebelum_pajak" if _safe(record, "laba_sebelum_pajak") else "revenue_proxy"

    return {
        "score": round(score, 2),
        "etr": round(etr * 100, 4),
        "etr_gap": round(etr_gap * 100, 4),
        "z_score": round(z, 4) if z is not None else None,
        "flag": flag,
        "flag_reason": f"ETR {etr*100:.1f}% — gap {etr_gap*100:.1f}% dari tarif {STATUTORY_TAX_RATE*100:.0f}%" if flag else None,
        "note": mode,
    }


def compute_net_margin(record):
    revenue = _safe_pos(record, "revenue")
    if revenue is None:
        return None

    laba_bersih = _safe(record, "laba_bersih")
    if laba_bersih is not None:
        margin = (laba_bersih / revenue) * 100
    else:
        beban  = _safe(record, "beban_pajak", 0)
        margin = ((revenue - beban) / revenue) * 100

    return None if (margin < -500 or margin > 200) else round(margin, 4)


def compute_margin_score(record, all_records):
    margin = compute_net_margin(record)
    if margin is None:
        return {
            "score": 0.0, "net_margin": None,
            "z_score": None, "peer_count": 0,
            "peer_mean": None, "flag": False,
            "flag_reason": None, "note": "data_tidak_tersedia",
        }

    sektor = record.get("sektor")
    peers  = ([r for r in all_records if r.get("sektor") == sektor]
              if sektor else all_records)
    if len(peers) < 3:
        peers = all_records

    peer_margins = [m for r in peers if (m := compute_net_margin(r)) is not None]

    score = 0.0
    z = None
    if len(peer_margins) >= 3:
        mean_m = statistics.mean(peer_margins)
        std_m  = statistics.stdev(peer_margins) if len(peer_margins) > 1 else 0
        z      = _zscore(margin, mean_m, std_m)
        score  = _z_to_pts(z) if (z is not None and z < 0) else 0.0  # negatif = suspicious

    flag = z is not None and z < -2.0

    return {
        "score":       round(score, 2),
        "net_margin":  margin,
        "z_score":     round(z, 4) if z is not None else None,
        "peer_count":  len(peer_margins),
        "peer_mean":   round(statistics.mean(peer_margins), 4) if peer_margins else None,
        "flag":        flag,
        "flag_reason": f"Net margin {margin:.1f}% — Z={z:.2f} (jauh di bawah peers)" if flag else None,
        "note":        f"sektor_{sektor}" if sektor else "all_company_peers",
    }

def compute_rp_haven_score(record):
    rp_total = _safe_pos(record, "rp_total")
    rp_haven = _safe(record, "rp_ke_tax_haven", 0) or 0.0

    if rp_total is None:
        return {
            "score": 0.0, "rp_total": None, "rp_haven": None,
            "haven_ratio": None, "flag": False,
            "flag_reason": None, "note": "data_rp_tidak_tersedia",
        }

    haven_ratio = min(1.0, max(0.0, rp_haven / rp_total))
    score = haven_ratio * 100.0
    flag  = haven_ratio > RP_HAVEN_THRESHOLD

    return {
        "score":       round(score, 2),
        "rp_total":    rp_total,
        "rp_haven":    rp_haven,
        "haven_ratio": round(haven_ratio * 100, 2),   # persen
        "flag":        flag,
        "flag_reason": f"RP ke tax haven {haven_ratio*100:.1f}% dari total RP" if flag else None,
        "note":        "rp_data_tersedia",
    }

def compute_de_ratio(record):
    utang   = _safe_pos(record, "total_utang")
    ekuitas = _safe_pos(record, "ekuitas")

    if utang and ekuitas:
        return round(utang / ekuitas, 4)

    aset = _safe_pos(record, "total_aset")
    if utang and aset and aset > utang:
        ekuitas_proxy = aset - utang
        if ekuitas_proxy > 0:
            return round(utang / ekuitas_proxy, 4)

    de = _safe(record, "de_ratio")
    return round(de, 4) if de is not None else None


def compute_implied_interest_rate(record):
    bunga = _safe_pos(record, "beban_bunga")
    utang = _safe_pos(record, "total_utang")
    if bunga is None or utang is None:
        return None
    rate = bunga / utang
    return None if rate > 5.0 else round(rate, 6)


def compute_debt_score(record, all_records: list) -> dict:
    de       = compute_de_ratio(record)
    impl_int = compute_implied_interest_rate(record)

    sub_scores = []
    flags      = []
    details    = {}

    if de is not None:
        if de > DE_SAFE_HARBOR:
            de_score = min(90.0, ((de - DE_SAFE_HARBOR) / DE_SAFE_HARBOR) * 40.0 + 40.0)
            flags.append(f"D/E ratio {de:.1f}x — melebihi safe harbor {DE_SAFE_HARBOR}:1 (PMK-169)")
        else:
            all_de = [d for r in all_records if (d := compute_de_ratio(r)) is not None]
            de_score = 0.0
            if len(all_de) >= 3:
                z = _zscore(de, statistics.mean(all_de),
                            statistics.stdev(all_de) if len(all_de) > 1 else 0)
                de_score = _z_to_pts(z) if (z and z > 0) else 0.0
        sub_scores.append(de_score)
        details["de_ratio"]   = de
        details["de_score"]   = round(de_score, 2)
        details["de_flag"]    = de > DE_SAFE_HARBOR

    if impl_int is not None:
        threshold = BI_RATE * 2
        if impl_int > threshold:
            ir_score = min(60.0, ((impl_int - threshold) / threshold) * 30.0 + 30.0)
            flags.append(
                f"Implied interest {impl_int*100:.1f}% — lebih dari 2× BI rate ({BI_RATE*100:.2f}%)"
            )
        else:
            ir_score = 0.0
        sub_scores.append(ir_score)
        details["implied_interest_pct"]    = round(impl_int * 100, 4)
        details["bi_rate_2x_threshold_pct"] = round(BI_RATE * 2 * 100, 2)
        details["interest_score"]          = round(ir_score, 2)
        details["interest_flag"]           = impl_int > threshold

    final = max(sub_scores) if sub_scores else 0.0

    return {
        "score":   round(final, 2),
        "flag":    len(flags) > 0,
        "flags":   flags,
        "details": details,
        "note":    "ok" if sub_scores else "data_tidak_tersedia",
    }


def compute_ownership_score(record) -> dict:
    haven_count   = int(_safe(record, "haven_node_count",   0) or 0)
    depth         = int(_safe(record, "ownership_depth",    0) or 0)
    mystery_count = int(_safe(record, "mystery_entity_count", 0) or 0)

    score = 0.0
    flags = []

    if haven_count > 0:
        score = max(score, min(100.0, haven_count * 20.0))
        flags.append(f"{haven_count} tax haven node dalam ownership chain")

    if depth > 2:
        score = max(score, min(100.0, (depth - 2) * 25.0))
        flags.append(f"Ownership depth {depth} layer — indikasi shell layering")

    if mystery_count > 0:
        score = max(score, min(100.0, mystery_count * 30.0))
        flags.append(f"{mystery_count} mystery entity — tidak cocok di subsidiary table")

    no_data = (haven_count == 0 and depth == 0 and mystery_count == 0)

    return {
        "score":            round(score, 2),
        "haven_node_count": haven_count,
        "ownership_depth":  depth,
        "mystery_entities": mystery_count,
        "flag":             score > 0,
        "flags":            flags,
        "note":             "data_tidak_tersedia" if no_data else "ok",
    }


def compute_conduct_score(record) -> dict:
    """
    Skor prior conduct (0–100).
    Kolom: tax_dispute_flag, court_verdict_flag, dtl_spike_flag.
    """
    dispute = bool(record.get("tax_dispute_flag", False))
    verdict = bool(record.get("court_verdict_flag", False))
    dtl     = bool(record.get("dtl_spike_flag", False))

    score = 0.0
    flags = []

    if dispute:
        score += 30.0
        flags.append("Sengketa pajak terdeteksi di filing (NLP)")
    if verdict:
        score += 35.0
        flags.append("Putusan pengadilan pajak ditemukan")
    if dtl:
        score += 20.0
        flags.append("Lonjakan Deferred Tax Liability terdeteksi")

    no_data = not (dispute or verdict or dtl)

    return {
        "score":         min(100.0, round(score, 2)),
        "tax_dispute":   dispute,
        "court_verdict": verdict,
        "dtl_spike":     dtl,
        "flag":          score > 0,
        "flags":         flags,
        "note":          "data_tidak_tersedia" if no_data else "ok",
    }


def compute_etr_persistence(company_history):
    if not company_history:
        return 0

    sorted_history = sorted(company_history, key=lambda r: r.get("year", 0), reverse=True)
    consecutive = 0
    for rec in sorted_history:
        etr = compute_etr(rec)
        if etr is not None and (STATUTORY_TAX_RATE - etr) > ETR_GAP_THRESHOLD:
            consecutive += 1
        else:
            break

    return consecutive

def compute_company_risk_score(
    record,
    all_records,
    company_history= None,
):
    history = company_history or [record]

    etr_res   = compute_etr_score(record, all_records)
    mar_res   = compute_margin_score(record, all_records)
    rp_res    = compute_rp_haven_score(record)
    debt_res  = compute_debt_score(record, all_records)
    own_res   = compute_ownership_score(record)
    cond_res  = compute_conduct_score(record)

    etr_consecutive = compute_etr_persistence(history)
    etr_score_adj   = _persistence_multiplier(etr_res["score"], etr_consecutive)

    raw_score = (
        etr_score_adj    * SCORE_WEIGHTS["etr"]      +
        mar_res["score"] * SCORE_WEIGHTS["margin"]   +
        rp_res["score"]  * SCORE_WEIGHTS["rp_haven"] +
        debt_res["score"]* SCORE_WEIGHTS["debt"]     +
        own_res["score"] * SCORE_WEIGHTS["ownership"]+
        cond_res["score"]* SCORE_WEIGHTS["conduct"]
    )
    final_score = round(min(100.0, max(0.0, raw_score)), 2)
    tier = _get_risk_tier(final_score)

    all_flags = []
    for res in [etr_res, mar_res, rp_res]:
        if res.get("flag_reason"):
            all_flags.append(res["flag_reason"])
    for res in [debt_res, own_res, cond_res]:
        all_flags.extend(res.get("flags", []))

    coverage = {
        "laba_sebelum_pajak": _safe(record, "laba_sebelum_pajak") is not None,
        "laba_bersih": _safe(record, "laba_bersih") is not None,
        "rp_data": _safe(record, "rp_total") is not None,
        "beban_bunga": _safe(record, "beban_bunga") is not None,
        "ownership_data": any([
            record.get("haven_node_count"),
            record.get("ownership_depth"),
            record.get("mystery_entity_count"),
        ]),
        "conduct_data": any([
            record.get("tax_dispute_flag"),
            record.get("court_verdict_flag"),
            record.get("dtl_spike_flag"),
        ]),
        "etr_mode": "laba_sebelum_pajak" if _safe(record, "laba_sebelum_pajak") else "revenue_proxy",
    }

    return {
        "code":record.get("code"),
        "name":record.get("name"),
        "year":record.get("year"),
        "sektor": record.get("sektor"),
        "risk_score": final_score,
        "risk_tier": tier,
        "components": {
            "etr": {
                **etr_res,
                "score_after_persistence": round(etr_score_adj, 2),
                "weight": SCORE_WEIGHTS["etr"],
                "weighted_contribution": round(etr_score_adj * SCORE_WEIGHTS["etr"], 2),
            },
            "margin": {
                **mar_res,
                "weight": SCORE_WEIGHTS["margin"],
                "weighted_contribution": round(mar_res["score"] * SCORE_WEIGHTS["margin"], 2),
            },
            "rp_haven": {
                **rp_res,
                "weight": SCORE_WEIGHTS["rp_haven"],
                "weighted_contribution": round(rp_res["score"] * SCORE_WEIGHTS["rp_haven"], 2),
            },
            "debt": {
                **debt_res,
                "weight": SCORE_WEIGHTS["debt"],
                "weighted_contribution": round(debt_res["score"] * SCORE_WEIGHTS["debt"], 2),
            },
            "ownership": {
                **own_res,
                "weight": SCORE_WEIGHTS["ownership"],
                "weighted_contribution": round(own_res["score"] * SCORE_WEIGHTS["ownership"], 2),
            },
            "conduct": {
                **cond_res,
                "weight": SCORE_WEIGHTS["conduct"],
                "weighted_contribution": round(cond_res["score"] * SCORE_WEIGHTS["conduct"], 2),
            },
        },
        "top_flags": all_flags[:5],
        "data_coverage": coverage,
        "persistence": {
            "etr_consecutive_years": etr_consecutive,
            "persistence_multiplier_applied": etr_consecutive >= 3,
        },
    }


def _group_by_code(all_records: list) -> dict:
    groups = {}
    for rec in all_records:
        code = rec.get("code")
        if code:
            groups.setdefault(code, []).append(rec)
    return groups


def compute_all_companies_overview(all_records):
    groups = _group_by_code(all_records)
    results = []

    for code, history in groups.items():
        latest = max(history, key=lambda r: r.get("year", 0))
        scored = compute_company_risk_score(latest, all_records, history)

        results.append({
            "code": scored["code"],
            "name": scored["name"],
            "year": scored["year"],
            "sektor":      scored["sektor"],
            "risk_score":  scored["risk_score"],
            "risk_tier":   scored["risk_tier"]["tier"],
            "risk_action": scored["risk_tier"]["action"],
            "top_flags":   scored["top_flags"],
            "etr_pct":     scored["components"]["etr"].get("etr"),
            "etr_gap_pct": scored["components"]["etr"].get("etr_gap"),
            "net_margin":  scored["components"]["margin"].get("net_margin"),
            "de_ratio":    scored["components"]["debt"]["details"].get("de_ratio"),
            "etr_mode":    scored["data_coverage"]["etr_mode"],
            "data_year":   latest.get("year"),
        })

    return sorted(results, key=lambda x: x["risk_score"], reverse=True)


def get_warning_counts(all_records):
    overview = compute_all_companies_overview(all_records)

    buckets = {"critical": [], "high": [], "medium": [], "low": []}
    for item in overview:
        tier = item.get("risk_tier", "low")
        if tier in buckets:
            buckets[tier].append({
                "code":  item["code"],
                "name":  item["name"],
                "score": item["risk_score"],
            })

    return {
        "critical": len(buckets["critical"]),
        "high":     len(buckets["high"]),
        "medium":   len(buckets["medium"]),
        "low":      len(buckets["low"]),
        "total":    len(overview),
        "breakdown": [
            {"tier": "critical", "count": len(buckets["critical"]), "companies": buckets["critical"]},
            {"tier": "high",     "count": len(buckets["high"]),     "companies": buckets["high"]},
            {"tier": "medium",   "count": len(buckets["medium"]),   "companies": buckets["medium"]},
            {"tier": "low",      "count": len(buckets["low"]),      "companies": buckets["low"]},
        ],
    }


def get_priority_review(all_records: list, top_n: int = 10) -> list:
    overview = compute_all_companies_overview(all_records)
    priority = [x for x in overview if x["risk_tier"] in ("critical", "high")]
    return priority[:top_n]


def get_financial_signals(
    record,
    all_records,
    company_history= None,
):
    history = company_history or [record]
    full = compute_company_risk_score(record, all_records, history)

    full["computed_metrics"] = {
        "etr_pct": full["components"]["etr"].get("etr"),
        "etr_gap_pct": full["components"]["etr"].get("etr_gap"),
        "statutory_rate_pct": STATUTORY_TAX_RATE * 100,
        "net_margin_pct": full["components"]["margin"].get("net_margin"),
        "de_ratio": full["components"]["debt"]["details"].get("de_ratio"),
        "de_safe_harbor": DE_SAFE_HARBOR,
        "implied_interest_pct": full["components"]["debt"]["details"].get("implied_interest_pct"),
        "bi_rate_pct": BI_RATE * 100,
        "rp_haven_ratio_pct": full["components"]["rp_haven"].get("haven_ratio"),
        "rp_haven_threshold_pct": RP_HAVEN_THRESHOLD * 100,
    }

    if len(history) > 1:
        full["trend"] = [
            {
                "year": rec.get("year"),
                "revenue": _safe(rec, "revenue"),
                "etr_pct": round(compute_etr(rec) * 100, 2) if compute_etr(rec) else None,
                "net_margin": compute_net_margin(rec),
                "de_ratio": compute_de_ratio(rec),
            }
            for rec in sorted(history, key=lambda r: r.get("year", 0))
        ]

    return full


def get_company_overview(
    record,
    all_records,
    company_history= None,
):
    history = company_history or [record]
    full    = compute_company_risk_score(record, all_records, history)

    COMPONENT_META = {
        "etr": ("ETR vs Statutory Rate", "Transfer Pricing"),
        "margin": ("Net Margin vs Peers", "Transfer Pricing"),
        "rp_haven": ("RP ke Tax Haven", "Transfer Pricing / Shell"),
        "debt": ("D/E Ratio & Interest Rate", "Debt Shifting"),
        "ownership": ("Ownership Structure", "Shell Layering"),
        "conduct": ("Prior Conduct", "Semua Metode"),
    }

    component_summary = [
        {
            "signal": label,
            "avoidance_method": method,
            "raw_score": full["components"][key]["score"],
            "weight": full["components"][key]["weight"],
            "weighted_contrib": full["components"][key]["weighted_contribution"],
            "flag": full["components"][key].get("flag", False),
            "data_available": full["components"][key].get("note") != "data_tidak_tersedia",
        }
        for key, (label, method) in COMPONENT_META.items()
    ]

    return {
        "code": full["code"],
        "name": full["name"],
        "year": full["year"],
        "risk_score": full["risk_score"],
        "risk_tier": full["risk_tier"],
        "component_summary": component_summary,
        "top_flags": full["top_flags"],
        "data_coverage": full["data_coverage"],
        "persistence": full["persistence"],
    }