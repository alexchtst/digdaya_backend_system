from flask import Blueprint, jsonify, request
from flasgger import swag_from
import pandas as pd

from api.scoring_engine import (
    get_financial_signals,
    get_company_overview,
)

from api.rbs_module import *

from api.db import (
    get_all_records, get_company_records
)

analysis_bp = Blueprint("analysis", __name__)

@analysis_bp.route("/recommendation/<string:code>", methods=["GET"])
@swag_from({
    "tags": ["Analysis"],
    "summary": "Get company risk recommendation by code",
    "description": "Mengambil risk score, label RBS, prediksi Naive Bayes, dan rekomendasi tindakan berdasarkan kode saham perusahaan. Z-score dihitung dari distribusi seluruh dataset.",
    "parameters": [
        {
            "name": "code",
            "in": "path",
            "type": "string",
            "required": True,
            "example": "AALI",
            "description": "Kode saham perusahaan (case-insensitive)"
        }
    ],
    "responses": {
        200: {
            "description": "Success",
            "examples": {
                "application/json": {
                    "code": "AALI",
                    "total_years": 1,
                    "thresholds": {
                        "p25": 0.407,
                        "p50": 0.4657,
                        "p75": 0.6283
                    },
                    "recommendations": [
                        {
                            "code": "AALI",
                            "name": "Astra Agro Lestari Tbk",
                            "year": 2023,
                            "composite_score": 1.1731,
                            "label_rbs": 3,
                            "label_nb": 3,
                            "final_label": 3,
                            "status": "Critical - Perlu Investigasi",
                            "recommendation": (
                                "Eskalasi segera ke tim investigasi. "
                                "Audit menyeluruh pada laporan pajak, "
                                "tax gap, dan struktur DE ratio. "
                                "Verifikasi keabsahan data sumber PDF."
                            )
                        }
                    ]
                }
            }
        },
        404: {
            "description": "Perusahaan tidak ditemukan",
            "examples": {
                "application/json": {
                    "error": "Company with code 'XXXX' not found"
                }
            }
        },
        500: {
            "description": "Internal server error / data kosong",
            "examples": {
                "application/json": {
                    "error": "No data found in database"
                }
            }
        }
    }
})

def get_company_recommendation_by_code(code: str):
    all_records = get_all_records()
    if not all_records:
        return jsonify({"error": "No data found in database"}), 404
 
    company_records = get_company_records(code.upper())
    if not company_records:
        return jsonify({"error": f"Company with code '{code}' not found"}), 404
 
    df = pd.DataFrame(all_records)
 
    df["tax_gap"] = (
        pd.to_numeric(df["pajak_terutang"], errors="coerce") -
        pd.to_numeric(df["pajak_dibayar"],  errors="coerce")
    ).abs()
 
    for col in OBSERVEN:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df[col].median())
 
    df = compute_zscore(df)
    df, thresholds = label_data(df)
 
    model = train_naive_bayes(df)
 
    company_df = df[df["code"] == code.upper()]
 
    results = []
    for _, row in company_df.iterrows():
        results.append(get_recommendation(row, model))
 
    return jsonify({
        "code": code.upper(),
        "total_years": len(results),
        "thresholds": {
            "p25": round(thresholds[0], 4),
            "p50": round(thresholds[1], 4),
            "p75": round(thresholds[2], 4),
        },
        "recommendations": results
    }), 200


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