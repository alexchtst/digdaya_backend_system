from flask import Blueprint, jsonify

triage_bp = Blueprint("triage", __name__)

@triage_bp.route("/warning", methods=["GET"])
def get_warning():
    """
    Get Warning Count
    ---
    responses:
      200:
        description: Return the critical, high, medium, low risk company
    """
    return jsonify({
        "message": "API IS RUNNING WELL",
    }), 200

@triage_bp.route("/priority-review", methods=["GET"])
def get_priority_review():
    """
    Get Priority Review
    ---
    responses:
      200:
        description: Return the most recomended (critical) to be reviewed
    """
    return jsonify({
        "message": "API IS RUNNING WELL",
    }), 200

@triage_bp.route("/all-company", methods=["GET"])
def get_all_company_analysis():
    """
    Get All Company Data Brief Analysis to be shown in Dashboard
    ---
    responses:
      200:
        description: Return all the company analysis (risk score, ...., status)
    """
    return jsonify({
        "message": "API IS RUNNING WELL",
    }), 200