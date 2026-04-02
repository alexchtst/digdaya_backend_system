from flask import Blueprint, jsonify, request
from flasgger import swag_from

from api.scoring_engine import (
    compute_all_companies_overview,
    get_warning_counts,
    get_priority_review,
)

from api.db import (
    collection, get_all_records
)

triage_bp = Blueprint("triage", __name__)

@triage_bp.route("/warning", methods=["GET"])
@swag_from({
    "tags": ["Triage"],
    "summary": "Get warning counts",
    "description": "Menghitung jumlah perusahaan berdasarkan risk tier",
    "responses": {
        200: {
            "description": "Success",
            "examples": {
                "application/json": {
                    "critical": 5,
                    "high": 10,
                    "medium": 20,
                    "low": 50
                }
            }
        }
    }
})
def get_warning():
    all_records = get_all_records()
    result = get_warning_counts(all_records)
    return jsonify(result), 200


@triage_bp.route("/priority-review", methods=["GET"])
@swag_from({
    "tags": ["Triage"],
    "summary": "Get priority review companies",
    "parameters": [
        {
            "name": "top_n",
            "in": "query",
            "type": "integer",
            "default": 10,
            "required": False,
            "description": "Jumlah perusahaan yang diambil"
        }
    ],
    "responses": {
        200: {
            "description": "Success",
            "examples": {
                "application/json": {
                    "count": 10,
                    "companies": [
                        {"code": "AALI", "risk_score": 85}
                    ]
                }
            }
        }
    }
})
def get_priority_review_route():
    top_n = request.args.get("top_n", 10, type=int)

    all_records = get_all_records()
    result = get_priority_review(all_records, top_n=top_n)

    return jsonify({
        "count": len(result),
        "companies": result
    }), 200


@triage_bp.route("/all-company", methods=["GET"])
@swag_from({
    "tags": ["Triage"],
    "summary": "Get all company overview",
    "parameters": [
        {
            "name": "tier",
            "in": "query",
            "type": "string",
            "required": False,
            "enum": ["critical", "high", "medium", "low"],
            "description": "Filter berdasarkan risk tier"
        },
        {
            "name": "sektor",
            "in": "query",
            "type": "string",
            "required": False,
            "description": "Filter berdasarkan sektor"
        }
    ],
    "responses": {
        200: {
            "description": "Success",
            "examples": {
                "application/json": {
                    "count": 100,
                    "companies": [
                        {
                            "code": "AALI",
                            "risk_score": 75,
                            "risk_tier": "medium"
                        }
                    ]
                }
            }
        }
    }
})
def get_all_company_analysis():
    tier_filter   = request.args.get("tier")
    sektor_filter = request.args.get("sektor")

    all_records = get_all_records()
    overview = compute_all_companies_overview(all_records)

    if tier_filter:
        overview = [c for c in overview if c["risk_tier"] == tier_filter]

    if sektor_filter:
        overview = [c for c in overview if c.get("sektor") == sektor_filter]

    return jsonify({
        "count": len(overview),
        "companies": overview
    }), 200