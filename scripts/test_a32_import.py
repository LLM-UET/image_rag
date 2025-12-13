"""
Test client for A32 API - sends import_file RPC request to S15.

Usage:
    python scripts/test_a32_import.py --file-id "3,01234567" --timeout 300
"""
import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path

import pika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class A32TestClient:
    """Test client for sending import_file RPC requests."""
    
    def __init__(self, rabbitmq_host, rabbitmq_port, rabbitmq_user, rabbitmq_pass, request_queue):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.request_queue = request_queue
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Create temporary queue for responses
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue
        
        self.response = None
        self.corr_id = None
        
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True
        )
    
    def on_response(self, ch, method, props, body):
        """Handle RPC response."""
        if self.corr_id == props.correlation_id:
            self.response = body
    
    def call(self, seaweed_file_id: str, timeout: int = 300):
        """Send import_file RPC request."""
        self.response = None
        self.corr_id = str(uuid.uuid4())
        
        request = {
            "method": "import_file",
            "params": {
                "seaweed_file_id": seaweed_file_id
            },
            "id": f"import_req_{self.corr_id[:8]}"
        }
        
        logger.info(f"Sending request: {json.dumps(request, indent=2)}")
        
        self.channel.basic_publish(
            exchange='',
            routing_key=self.request_queue,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(request, ensure_ascii=False)
        )
        
        # Wait for response
        logger.info(f"Waiting for response (timeout: {timeout}s)...")
        self.connection.process_data_events(time_limit=timeout)
        
        if self.response is None:
            raise TimeoutError(f"No response received within {timeout}s")
        
        return json.loads(self.response)


def main():
    parser = argparse.ArgumentParser(description="Test A32 import_file RPC")
    parser.add_argument('--file-id', required=True, help='SeaweedFS file ID (e.g., "3,01234567")')
    parser.add_argument('--timeout', type=int, default=300, help='RPC timeout in seconds')
    parser.add_argument('--host', default=os.getenv('RABBITMQ_HOST', 'localhost'))
    parser.add_argument('--port', type=int, default=int(os.getenv('RABBITMQ_PORT', '5672')))
    parser.add_argument('--user', default=os.getenv('RABBITMQ_USER', 'guest'))
    parser.add_argument('--pass', dest='password', default=os.getenv('RABBITMQ_PASS', 'guest'))
    parser.add_argument('--queue', default=os.getenv('FILE_IMPORT_REQUEST_QUEUE', 'file_import_requests'))
    args = parser.parse_args()
    
    client = A32TestClient(
        rabbitmq_host=args.host,
        rabbitmq_port=args.port,
        rabbitmq_user=args.user,
        rabbitmq_pass=args.password,
        request_queue=args.queue
    )
    
    try:
        response = client.call(seaweed_file_id=args.file_id, timeout=args.timeout)
        
        logger.info("=" * 60)
        logger.info("Response received:")
        print(json.dumps(response, indent=2, ensure_ascii=False))
        logger.info("=" * 60)
        
        result = response.get('result', {})
        if result.get('status') == 'success':
            content = result.get('content', {})
            logger.info(f"✓ Success: {content.get('extracted_count', 0)} packages extracted")
            if content.get('warnings'):
                logger.warning(f"Warnings: {content['warnings']}")
        else:
            logger.error(f"✗ Error: {result.get('content', {}).get('error', 'Unknown error')}")
        
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        client.connection.close()


if __name__ == '__main__':
    main()
