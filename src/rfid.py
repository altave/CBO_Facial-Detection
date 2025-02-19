from flask import Flask, request, jsonify
import threading
import time
import logging
import logging.handlers
import queue
from datetime import datetime
import uuid
import os
import sys
from rabbit import RabbitMQ

# Read environment variables
src_id = os.environ.get("SRC_ID")
queue_name = os.environ.get("RFID_QUEUE")

app = Flask(__name__)

# Global variable to store received data
received_data_store = []
data_lock = threading.Lock()  # Lock for thread-safe operations

# **Thread-Safe Logging Setup**
log_queue = queue.Queue()


class QueueListenerHandler(logging.handlers.QueueHandler):
    """Custom logging handler that sends logs to a queue."""

    def emit(self, record):
        super().emit(record)
        sys.stdout.flush()  # Ensure logs are immediately written


# Configure the logger
logger = logging.getLogger("rfid_logger")
logger.setLevel(logging.INFO)

# Create a queue handler and add it to the logger
queue_handler = QueueListenerHandler(log_queue)
logger.addHandler(queue_handler)

# Also log to a file
file_handler = logging.FileHandler("rfid_monitor.log", mode="a")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Start a QueueListener in the main thread
queue_listener = logging.handlers.QueueListener(log_queue, file_handler)
queue_listener.start()

# RabbitMQ Client Initialization
try:
    rabbit_client = RabbitMQ(
        host='rabbitmq',
        port=5672,
        username='guest',
        password='guest',
        queue_name=queue_name
    )
except Exception as e:
    logger.error(f"Failed to initialize RabbitMQ client: {e}")
    rabbit_client = None


def generate_uuid_and_timestamp():
    """Generate a unique UUID and a UNIX timestamp."""
    unique_id = str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp())
    return unique_id, timestamp

# Helper function to convert timestamp to UNIX time


def convert_to_unix_timestamp(timestamp_str):
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        return int(dt.timestamp())
    except ValueError as e:
        logger.error(f"Error converting timestamp: {e}")
        return None

# **Flask Endpoints**


@app.route('/rfid', methods=['POST'])
def receive_readings():
    """Receive RFID readings via HTTP POST request."""
    global received_data_store
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response code": 400, "status": "error", "msg": "No data provided"}), 400

        with data_lock:
            received_data_store.extend(data)  # Append received data

        return jsonify({"response code": 200, "status": "success", "msg": "Data received successfully"}), 200
    except Exception as e:
        logger.error(f"Error processing /rfid request: {e}")
        return jsonify({"response code": 500, "status": "error", "msg": str(e)}), 500


@app.route('/clear_log_post', methods=['POST'])
def clear_log_post():
    """Clear received RFID data."""
    global received_data_store
    with data_lock:
        received_data_store.clear()
    logger.info("Clear log request received.")
    return jsonify({"response code": 200, "status": "success", "msg": "Buffer cleared successfully."}), 200


@app.route('/restart', methods=['POST'])
def restart_module():
    """Restart the RFID module."""
    action = request.form.get('acao')
    if action == 'confirma':
        logger.info("Restart request confirmed.")
        return jsonify({"response code": 200, "status": "success", "msg": "System restarted successfully."}), 200
    else:
        return jsonify({"response code": 400, "status": "error", "msg": "Invalid or missing action."}), 400


@app.route('/shutdown', methods=['POST'])
def shutdown_module():
    """Shutdown the RFID module."""
    action = request.form.get('acao')
    if action == 'confirma':
        logger.info("Shutdown request confirmed.")
        return jsonify({"response code": 200, "status": "success", "msg": "System shutdown successfully."}), 200
    else:
        return jsonify({"response code": 400, "status": "error", "msg": "Invalid or missing action."}), 400

# **Thread Function: Process and Send Data**


def send_data():
    """Continuously send stored RFID readings to RabbitMQ."""
    while True:
        with data_lock:
            if received_data_store:
                for record in received_data_store:
                    epc_hex = record.get("reading_epc_hex")
                    timestamp = record.get("reading_timestamp")
                    unix_timestamp = convert_to_unix_timestamp(timestamp)

                    if epc_hex and unix_timestamp is not None:
                        uuid, timestamp_u = generate_uuid_and_timestamp()
                        message = {
                            "uuid": uuid,
                            "rfid": epc_hex,
                            "timestamp": unix_timestamp,
                            "src_id": src_id
                        }
                        if rabbit_client:
                            rabbit_client.send_with_retry(message)
                            logger.info(f"Sent message to RabbitMQ: {message}")
                        else:
                            logger.error("RabbitMQ client is not initialized.")
                    else:
                        logger.warning(f"Invalid data in record: {record}")

                logger.info("Current received data: %s", received_data_store)
                received_data_store.clear()  # Clear data after processing
        time.sleep(5)  # Process every 5 seconds

# **Start Flask and the Thread**


def start_rfid():
    """Start the RFID Flask service and background processing thread."""
    logger.info("Starting RFID Service...")

    # Start the data processing thread
    threading.Thread(target=send_data, daemon=False).start()

    # Start the Flask app
    app.run(host='0.0.0.0', port=5000)


if __name__ == "__main__":
    start_rfid()
