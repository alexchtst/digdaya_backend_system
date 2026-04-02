from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from routes.triage_route import triage_bp as triage_route
from routes.analysis_route import analysis_bp as analysis_route

app = Flask(__name__)
swagger = Swagger(app)
CORS(app, origins=["*"])

@app.route("/")
def home():
    """
    Home Endpoint
    ---
    responses:
      200:
        description: Return the api system status and documentation
    """
    return jsonify({
        "message": "API IS RUNNING WELL",
        "hosted-api-documentation": "nanti",
        "local-api-documentation": "http://localhost:5000/apidocs"
    }), 200

app.register_blueprint(triage_route, url_prefix="/triage")
app.register_blueprint(analysis_route, url_prefix="/analysis")

if __name__ == "__main__":
    app.run(debug=True)
