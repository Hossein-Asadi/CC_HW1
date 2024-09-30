from flask import Flask, request, jsonify
from database import get_db
from tasks import send_to_queue

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_image():
    email = request.form.get('email')
    image = request.files['image']

    if not email or not image:
        return jsonify({"error": "Email and image are required"}), 400

    print(1)    

    db = get_db()
    print(2)
    request_id = db.requests.insert_one({
        "email": email,
        "image_url": f"/images/{image.filename}",
        "status": "pending",
        "caption": None,
        "new_image_url": None
    }).inserted_id
    print(3)
    image.save(f"static/images/{image.filename}")

    send_to_queue(str(request_id))

    return jsonify({"message": "Image uploaded successfully!", "request_id": str(request_id)})

@app.route('/status/<request_id>', methods=['GET'])
def check_status(request_id):
    db = get_db()
    request_data = db.requests.find_one({"_id": request_id})

    if not request_data:
        return jsonify({"error": "Invalid request ID"}), 404

    return jsonify({
        "status": request_data["status"],
        "caption": request_data["caption"],
        "new_image_url": request_data["new_image_url"]
    })

if __name__ == '__main__':
    app.run(debug=True)
