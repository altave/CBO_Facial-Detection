import os
import glob
import rabbit as rabbit
import time
import logging
import uuid
import sys
from datetime import datetime

# Use the same logger as the main script
logger = logging.getLogger("main_logger")

src_id = os.environ.get("SRC_ID")
queue = os.environ.get("FACIAL_ID_QUEUE")


def get_all_files(folder_path, file_pattern="*.jpg"):
    return glob.glob(os.path.join(folder_path, file_pattern))


def generate_uuid_and_timestamp():
    unique_id = str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp())
    return unique_id, timestamp


def start_face_id():
    folder_path = "/app/facial_detection"
    rabbit_client = rabbit.RabbitMQ(
        host='rabbitmq',
        port=5672,
        username='guest',
        password='guest',
        queue_name=queue
    )

    logger.info(f"Monitoring folder: {folder_path}")

    while True:
        files = get_all_files(folder_path)
        if files:
            for file_path in files:
                uuid, timestamp = generate_uuid_and_timestamp()
                data = {
                    "title": "Facial Detection",
                    "uuid": uuid,
                    "timestamp": timestamp,
                    "src_id": src_id
                }
                try:
                    rabbit_client.send_alert(data, file_path)
                    logger.info(
                        f"Successfully sent alert for file: {file_path} with UUID: {uuid}")
                    os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                time.sleep(1)
        time.sleep(5)
