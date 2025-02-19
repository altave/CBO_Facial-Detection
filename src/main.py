import logging
import logging.handlers
import threading
import queue
import time
import os
import face_id
import rfid
import sys

# Create a thread-safe logging queue
log_queue = queue.Queue()

# Define a QueueHandler to manage logging messages


class QueueListenerHandler(logging.handlers.QueueHandler):
    """Custom logging handler that sends logs to a queue."""

    def emit(self, record):
        super().emit(record)
        sys.stdout.flush()  # Ensure logs are immediately written


# Configure the logger
logger = logging.getLogger("main_logger")
logger.setLevel(logging.INFO)

# Create a queue handler and add it to the logger
queue_handler = QueueListenerHandler(log_queue)
logger.addHandler(queue_handler)

# Also log to a file
file_handler = logging.FileHandler("monitor.log", mode="a")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Start a QueueListener in the main thread
queue_listener = logging.handlers.QueueListener(log_queue, file_handler)
queue_listener.start()

# Read environment variables
face_id_start = os.environ.get("FACE_ID_ACTIVATED")
rfid_start = os.environ.get("RFID_ACTIVATED")

# Start threads for face_id and RFID
if face_id_start:
    logger.info("Starting FACE_DETECTION")
    threading.Thread(target=face_id.start_face_id, daemon=False).start()

if rfid_start:
    logger.info("Starting RFID")
    threading.Thread(target=rfid.start_rfid, daemon=False).start()

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("Program terminated by user.")
    queue_listener.stop()  # Ensure logs are flushed before exit
