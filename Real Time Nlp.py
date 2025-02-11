from fastapi import FastAPI, HTTPException
from transformers import pipeline
import uvicorn
import onnxruntime as ort
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from kafka import KafkaConsumer, KafkaProducer
import json
import os

app = FastAPI()

# Load tokenizer and model optimized with ONNX
MODEL_PATH = os.getenv("MODEL_PATH", "/app/onnx_models/phishing_detection.onnx")
TOKENIZER_PATH = os.getenv("TOKENIZER_PATH", "distilbert-base-uncased")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
INPUT_TOPIC = os.getenv("INPUT_TOPIC", "threat-detection-input")
OUTPUT_TOPIC = os.getenv("OUTPUT_TOPIC", "threat-detection-output")

# Initialize Kafka producer
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
session = ort.InferenceSession(MODEL_PATH)
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))

# Function to make predictions
def predict(text: str):
    inputs = tokenizer(text, return_tensors="np", padding=True, truncation=True)
    ort_inputs = {session.get_inputs()[0].name: inputs["input_ids"].astype(np.int64)}
    outputs = session.run(None, ort_inputs)
    prediction = torch.softmax(torch.tensor(outputs[0]), dim=1).tolist()[0]
    return {"label": "phishing" if prediction[1] > 0.5 else "safe", "confidence": prediction[1]}

@app.post("/detect-threat/")
def detect_threat(text: str):
    """Detects potential threats in a given text using an optimized ONNX model."""
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    result = predict(text)
    return {"text": text, "prediction": result}

# Kafka Consumer to process streaming data
def consume_messages():
    consumer = KafkaConsumer(INPUT_TOPIC, bootstrap_servers=KAFKA_BROKER, value_deserializer=lambda m: json.loads(m.decode('utf-8')))
    for message in consumer:
        text = message.value.get("text", "")
        if text:
            result = predict(text)
            producer.send(OUTPUT_TOPIC, {"text": text, "prediction": result})

if __name__ == "__main__":
    import threading
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
