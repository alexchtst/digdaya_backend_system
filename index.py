from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from api.triage_route import triage_bp as triage_route
from api.analysis_route import analysis_bp as analysis_route

app = Flask(__name__)
swagger = Swagger(app)
CORS(app, origins=["*"])

app.register_blueprint(triage_route, url_prefix="/triage")
app.register_blueprint(analysis_route, url_prefix="/analysis")

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
        "hosted-api-documentation": "https://digdaya-backend-system.vercel.app/apidocs",
        "local-api-documentation": "http://localhost:5000/apidocs"
    }), 200

if __name__ == "__main__":
    app.run(debug=True)
