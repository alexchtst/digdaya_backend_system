from flask import Blueprint, jsonify

analysis_bp = Blueprint("analysis", __name__)

@analysis_bp.route("/overview", methods=["GET"])
def get_warning():
    """
    Get Company Risk Overview
    ---
    responses:
      200:
        description: Return the critical, high, medium, low risk company
    """
    return jsonify({
        "message": "API IS RUNNING WELL",
    }), 200

@analysis_bp.route("/signal", methods=["GET"])
def get_signal():
    """
    Get Company Financial Signal
    ---
    responses:
      200:
        description: Return the full analysis of company
    """
    return jsonify({
        "message": "API IS RUNNING WELL",
    }), 200