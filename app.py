from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
import boto3
import pika
import requests
from flask_mail import Mail, Message
from dotenv import load_dotenv
from urllib.parse import quote

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MongoDB Connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client['my-app']
requests_collection = db['requests']

# Liara Object Storage Configuration
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("LIARA_ENDPOINT"),
    aws_access_key_id=os.getenv("LIARA_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("LIARA_SECRET_KEY"),
)

# RabbitMQ Connection
rabbitmq_url = os.getenv("RABBITMQ_URL")
params = pika.URLParameters(rabbitmq_url)
connection = pika.BlockingConnection(params)
channel = connection.channel()

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)


# Route to upload file to Liara Object Storage
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    s3.upload_fileobj(file, os.getenv("LIARA_BUCKET_NAME"), file.filename)
    return jsonify({"message": "File uploaded successfully", "filename": file.filename}), 200


# Route to send task to RabbitMQ
@app.route('/send_task', methods=['POST'])
def send_task():
    data = request.json
    channel.basic_publish(exchange='', routing_key='task_queue', body=str(data))
    return jsonify({"message": "Task sent to RabbitMQ"}), 200


# Route to generate image caption using Hugging Face
@app.route('/caption', methods=['POST'])
def generate_caption():
    image_url = request.json['image_url']
    model_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
    
    headers = {"Authorization": f"Bearer {os.getenv('HF_API_KEY')}"}
    response = requests.post(model_url, headers=headers, json={"inputs": image_url})
    
    if response.status_code == 200:
        caption = response.json()[0]['generated_text']
        # Update database with caption
        requests_collection.update_one({"_id": request.json['request_id']}, {"$set": {"caption": caption}})
        return jsonify({"caption": caption}), 200
    else:
        return jsonify({"error": "Failed to generate caption"}), 500


# Route to generate image from caption using Hugging Face
@app.route('/generate_image', methods=['POST'])
def generate_image():
    caption = request.json['caption']
    model_url = "https://api-inference.huggingface.co/models/ZB-Tech/Text-to-Image"
    
    headers = {"Authorization": f"Bearer {os.getenv('HF_API_KEY')}"}
    response = requests.post(model_url, headers=headers, json={"inputs": caption})
    
    if response.status_code == 200:
        generated_image_url = response.json()['generated_image_url']
        # Update the database with the generated image URL
        requests_collection.update_one({"_id": request.json['request_id']}, {"$set": {"image_url": generated_image_url}})
        return jsonify({"image_url": generated_image_url}), 200
    else:
        return jsonify({"error": "Failed to generate image"}), 500


# Route to send email with the image URL
@app.route('/send_email', methods=['POST'])
def send_email():
    email = request.json['email']
    image_url = request.json['image_url']
    
    msg = Message('Your generated image', sender='hosseinasadi0109@gmail.com', recipients=[email])
    msg.body = f"Here is your image: {image_url}"
    mail.send(msg)
    
    return jsonify({"message": "Email sent successfully"}), 200


if __name__ == '__main__':
    app.run(debug=True)
