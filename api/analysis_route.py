from flask import Blueprint, jsonify, request
from flasgger import swag_from

from api.scoring_engine import (
    get_financial_signals,
    get_company_overview,
)

from api.db import (
    get_all_records, get_company_records
)

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/overview", methods=["GET"])
@swag_from({
    "tags": ["Analysis"],
    "summary": "Get company risk overview",
    "description": "Mengambil risk score, tier, dan ringkasan analisis perusahaan",
    "parameters": [
        {
            "name": "code",
            "in": "query",
            "type": "string",
            "required": True,
            "example": "AALI",
            "description": "Kode saham perusahaan"
        },
        {
            "name": "year",
            "in": "query",
            "type": "integer",
            "required": False,
            "example": 2023,
            "description": "Tahun laporan (default = terbaru)"
        }
    ],
    "responses": {
        200: {
            "description": "Success",
            "examples": {
                "application/json": {
                    "code": "AALI",
                    "year": 2023,
                    "risk_score": 78.5,
                    "risk_tier": "medium",
                    "flags": ["ETR tinggi", "Margin rendah"]
                }
            }
        },
        400: {
            "description": "Bad request"
        },
        404: {
            "description": "Data tidak ditemukan"
        }
    }
})

def get_company_overview_route():
    code = request.args.get("code", "").upper()
    year = request.args.get("year", type=int)

    if not code:
        return jsonify({"error": "Parameter 'code' wajib diisi"}), 400

    all_records     = get_all_records()
    company_history = get_company_records(code)

    if not company_history:
        return jsonify({"error": f"Perusahaan '{code}' tidak ditemukan"}), 404

    if year:
        record = next((r for r in company_history if r.get("year") == year), None)
        if not record:
            return jsonify({"error": f"Data tahun {year} tidak ditemukan"}), 404
    else:
        record = max(company_history, key=lambda r: r.get("year", 0))

    result = get_company_overview(record, all_records, company_history)
    return jsonify(result), 200


@analysis_bp.route("/signal", methods=["GET"])
@swag_from({
    "tags": ["Analysis"],
    "summary": "Get full financial signals",
    "description": "Analisis lengkap sinyal keuangan perusahaan termasuk trend multi-tahun",
    "parameters": [
        {
            "name": "code",
            "in": "query",
            "type": "string",
            "required": True,
            "example": "AALI"
        },
        {
            "name": "year",
            "in": "query",
            "type": "integer",
            "required": False,
            "example": 2023
        }
    ],
    "responses": {
        200: {
            "description": "Success",
            "examples": {
                "application/json": {
                    "code": "AALI",
                    "year": 2023,
                    "signals": {
                        "etr": "abnormal",
                        "de_ratio": "tinggi"
                    },
                    "trend": [
                        {"year": 2021, "etr": 80},
                        {"year": 2022, "etr": 85},
                        {"year": 2023, "etr": 91}
                    ]
                }
            }
        },
        400: {
            "description": "Bad request"
        },
        404: {
            "description": "Data tidak ditemukan"
        }
    }
})

def get_signal():
    code = request.args.get("code", "").upper()
    year = request.args.get("year", type=int)

    if not code:
        return jsonify({"error": "Parameter 'code' wajib diisi"}), 400

    all_records     = get_all_records()
    company_history = get_company_records(code)

    if not company_history:
        return jsonify({"error": f"Perusahaan '{code}' tidak ditemukan"}), 404

    if year:
        record = next((r for r in company_history if r.get("year") == year), None)
        if not record:
            return jsonify({"error": f"Data tahun {year} tidak ditemukan"}), 404
    else:
        record = max(company_history, key=lambda r: r.get("year", 0))

    result = get_financial_signals(record, all_records, company_history)
    return jsonify(result), 200