import logging
import pika
import time
import sys
from retrying import retry


class RabbitMQ:
    def __init__(self, host, port, username, password, queue_name):
        """
        Initialize the RabbitMQ client.

        Args:
            host (str): RabbitMQ server hostname.
            port (int): RabbitMQ server port.
            username (str): Username for RabbitMQ.
            password (str): Password for RabbitMQ.
            queue_name (str): Queue name to publish messages to.
        """
        self.host = host
        self.port = port
        self.queue_name = queue_name
        self.credentials = pika.PlainCredentials(username, password)
        self.connection = None
        self.channel = None

    def connect(self):
        """
        Establish a connection and channel to RabbitMQ.
        """
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, port=self.port, credentials=self.credentials, heartbeat=60)
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            logging.info(f"Connected to RabbitMQ and declared queue: {self.queue_name}")
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def reconnect(self):
        """
        Reconnect to RabbitMQ if the connection or channel is closed.
        """
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logging.info("Closed existing RabbitMQ connection.")
        except Exception as e:
            logging.warning(f"Failed to close existing connection: {e}")

        logging.info("Attempting to reconnect to RabbitMQ...")
        self.connect()

    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10000, stop_max_attempt_number=5)
    def send_with_retry(self, metadata, file_path=None):
        """
        Attempt to send a message to RabbitMQ with retries.

        Args:
            metadata (dict): Metadata information to include in the message.
            file_path (str): Path to the file to send as binary data.
        """
        logging.info(f"Retrying message send for {file_path}...")
        self.send_alert(metadata, file_path)

    def send_alert(self, metadata, file_path):
        """
        Send an alert message to RabbitMQ.

        Args:
            metadata (dict): Metadata information to include in the message.
            file_path (str): Path to the file to send as binary data.
        """

        try:
            self.connect()
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Failed to connect to RabbitMQ: {e}")
            self.reconnect()

        try:
            if not self.connection or self.connection.is_closed:
                logging.warning("RabbitMQ connection is closed. Attempting to reconnect...")
                self.reconnect()

            if not self.channel or self.channel.is_closed:
                logging.warning("RabbitMQ channel is closed. Attempting to reconnect...")
                self.reconnect()
            if file_path:
                with open(file_path, 'rb') as file:
                    binary_data = file.read()
            else: binary_data = ''

            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=binary_data,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent message
                    headers=metadata
                )
            )
            time.sleep(0.5)
            logging.info(f"Message sent successfully for {file_path}")
        except pika.exceptions.AMQPError as e:
            logging.error(f"Failed to publish message for file {file_path}: {e}", exc_info=True)
            raise
        finally:

            self.close()

    def close(self):
        """
        Gracefully close the connection to RabbitMQ.
        """
        if self.connection and self.connection.is_open:
            try:
                self.connection.close()
                logging.info("RabbitMQ connection closed.")
            except Exception as e:
                logging.error(f"Error closing RabbitMQ connection: {e}")


# Example usage:
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        rabbit_client = RabbitMQ(
            host='localhost',
            port=5672,
            username='guest',
            password='guest',
            queue_name='cbo.face-detection'
        )
        metadata = {"title": "Test Message"}
        rabbit_client.send_with_retry(metadata)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        rabbit_client.close()
