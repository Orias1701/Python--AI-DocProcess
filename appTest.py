from flask import Flask, request, jsonify
from flask_cors import CORS

import appCalled

app = Flask(__name__)
CORS(app)

@app.route("/process_pdf", methods=["POST"])
def process_pdf():
    """API nhận file PDF và trả về summary + category."""
    if "file" not in request.files:
        return jsonify({"error": "Thiếu file PDF"}), 400

    pdf_file = request.files["file"]
    if not pdf_file.filename.endswith(".pdf"):
        return jsonify({"error": "File không hợp lệ"}), 400

    try:
        pdf_bytes = pdf_file.read()
        result = appCalled.fileProcess(pdf_bytes)
        return jsonify({
            "status": "success",
            "checkstatus": result["checkstatus"],
            "metrics": result["metrics"],
            "summary": result["summary"],
            "category": result["category"],
            "top_candidates": result["reranked"]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
