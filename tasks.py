import pika
import requests
from database import get_db

# RabbitMQ Producer
def send_to_queue(request_id):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='image_tasks')

    channel.basic_publish(exchange='',
                          routing_key='image_tasks',
                          body=request_id)

    connection.close()

# RabbitMQ Consumer (Captioning and Image Generation)
def process_task():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='image_tasks')

    def callback(ch, method, properties, body):
        request_id = body.decode()
        db = get_db()

        # Fetch the request from MongoDB
        request_data = db.requests.find_one({"_id": request_id})

        if request_data:
            # 1. Image Captioning (using Hugging Face API)
            image_url = request_data['image_url']
            caption = generate_caption(image_url)
            
            # Update caption in MongoDB
            db.requests.update_one({"_id": request_id}, {"$set": {"caption": caption, "status": "ready"}})

            # 2. Text to Image Generation
            new_image_url = generate_image(caption)
            
            # Update new image URL and set status to done
            db.requests.update_one({"_id": request_id}, {"$set": {"new_image_url": new_image_url, "status": "done"}})

    channel.basic_consume(queue='image_tasks', on_message_callback=callback, auto_ack=True)

    print('Waiting for tasks...')
    channel.start_consuming()

# Hugging Face API for Caption Generation
def generate_caption(image_url):
    url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
    headers = {"Authorization": f"Bearer YOUR_HUGGING_FACE_API_TOKEN"}
    response = requests.post(url, headers=headers, json={"image_url": image_url})
    return response.json()[0]['generated_text']

# Hugging Face API for Image Generation
def generate_image(caption):
    url = "https://api-inference.huggingface.co/models/kothariyashhh/GenAi-Texttoimage"
    headers = {"Authorization": f"Bearer YOUR_HUGGING_FACE_API_TOKEN"}
    response = requests.post(url, headers=headers, json={"inputs": caption})
    return response.json()['generated_image']
