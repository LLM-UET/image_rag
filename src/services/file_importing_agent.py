"""
S15 - File Importing AI Agent Service

Implements A32 API: listens to RabbitMQ queue for import_file requests,
downloads files from SeaweedFS, extracts telecom packages, and returns
structured results via RPC response.

Usage:
    python src/services/file_importing_agent.py
"""
import json
import logging
import os
import sys
import tempfile
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import pika

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.telecom_service import TelecomDocumentService
from config.settings import settings
from api.seaweedfs_client import SeaweedFSClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FileImportingAgent:
    """
    S15 Service - File Importing AI Agent.
    
    Listens to RabbitMQ queue for import_file RPC requests,
    downloads files from SeaweedFS, processes them, and returns results.
    """
    
    def __init__(
        self,
        rabbitmq_host: str,
        rabbitmq_port: int,
        rabbitmq_user: str,
        rabbitmq_pass: str,
        request_queue: str,
        response_queue: str,
        seaweed_master: str,
        model_name: str = "gpt-4o-mini"
    ):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.seaweed_master = seaweed_master
        self.model_name = model_name
        
        # Initialize extraction service
        self.extraction_service = TelecomDocumentService(model_name=model_name)
        # Initialize SeaweedFS client (allow overriding volume URL)
        self.seaweed_volume = os.getenv('SEAWEED_VOLUME_URL')
        self.seaweed_client = SeaweedFSClient(master_url=self.seaweed_master, volume_url=self.seaweed_volume)
        
        # RabbitMQ connection
        self.connection = None
        self.channel = None
        
        logger.info(f"FileImportingAgent initialized (queue: {request_queue})")
    
    def connect_rabbitmq(self):
        """Establish RabbitMQ connection."""
        credentials = pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass)
        parameters = pika.ConnectionParameters(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Declare request queue
        self.channel.queue_declare(queue=self.request_queue, durable=True)
        self.channel.queue_declare(queue=self.response_queue, durable=True)
        
        logger.info(f"Connected to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}")
    
    def download_from_seaweed(self, file_id: str) -> Optional[str]:
        """
        Download file from SeaweedFS.
        
        Args:
            file_id: SeaweedFS file ID (e.g., "3,01234567")
        
        Returns:
            Path to downloaded temporary file, or None on error
        """
        try:
            # Use SeaweedFSClient which handles publicUrl / lookup and fallbacks
            logger.info(f"Downloading file id from SeaweedFS: {file_id} (volume override: {self.seaweed_volume})")

            content, headers = self.seaweed_client.download_file(file_id)

            # Try to get original filename from Content-Disposition header
            suffix = '.pdf'  # Default for telecom documents
            content_disp = headers.get('Content-Disposition', '')
            if content_disp and 'filename=' in content_disp:
                # Extract filename from Content-Disposition
                import re
                match = re.search(r'filename="?([^"]+)"?', content_disp)
                if match:
                    original_name = match.group(1)
                    suffix = Path(original_name).suffix or '.pdf'
                    logger.info(f"Extracted suffix from Content-Disposition: {suffix}")
            
            # Fallback: detect from content-type header
            if suffix == '.pdf':
                content_type = headers.get('Content-Type', '')
                if content_type:
                    type_mapping = {
                        'application/pdf': '.pdf',
                        'image/png': '.png',
                        'image/jpeg': '.jpg',
                        'text/plain': '.txt'
                    }
                    suffix = type_mapping.get(content_type, suffix)
                    logger.info(f"Using suffix from Content-Type: {content_type} -> {suffix}")
            
            # Final fallback: detect from magic bytes
            if suffix == '.pdf' and not content.startswith(b'%PDF'):
                suffix = self._detect_suffix(content)
                logger.info(f"Detected suffix from magic bytes: {suffix}")

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file.write(content)
            temp_file.close()
            
            logger.info(f"Downloaded to: {temp_file.name} (size={len(content)} bytes, suffix={suffix})")
            return temp_file.name

        except Exception as e:
            logger.error(f"Failed to download {file_id}: {e}")
            return None
    
    def _guess_suffix(self, content_type: str) -> str:
        """Guess file suffix from content type."""
        mapping = {
            'application/pdf': '.pdf',
        }
        return mapping.get(content_type, '.bin')

    def _detect_suffix(self, content: bytes, content_type: Optional[str] = None) -> str:
        """
        Detect a reasonable file suffix from file bytes or Content-Type header.
        Uses simple magic-number checks for common types (PDF, PNG, JPEG, ZIP, GIF, TXT).
        Falls back to `.bin` when unknown.
        """
        # Prefer Content-Type when available
        if content_type:
            mapping = {
                'application/pdf': '.pdf',
                'image/png': '.png',
                'image/jpeg': '.jpg',
                'application/zip': '.zip',
                'text/plain': '.txt',
            }
            if content_type in mapping:
                logger.info(f"Detected suffix from Content-Type: {content_type} -> {mapping[content_type]}")
                return mapping[content_type]

        # Binary signatures
        header = content[:16] if len(content) >= 16 else content
        logger.debug(f"Detecting suffix from magic bytes: {header!r}")
        
        if content.startswith(b'%PDF'):
            logger.info(f"Detected PDF from magic bytes")
            return '.pdf'
        if content.startswith(b'\x89PNG'):
            logger.info(f"Detected PNG from magic bytes")
            return '.png'
        if content.startswith(b'\xff\xd8'):
            logger.info(f"Detected JPEG from magic bytes")
            return '.jpg'
        if content.startswith(b'PK\x03\x04'):
            logger.info(f"Detected ZIP from magic bytes")
            return '.zip'
        if content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
            logger.info(f"Detected GIF from magic bytes")
            return '.gif'

        # Heuristic for plain text
        try:
            sample = content[:512]
            if all(b < 128 for b in sample) and b'\n' in sample:
                logger.info(f"Detected text file from heuristic")
                return '.txt'
        except Exception:
            pass

        logger.warning(f"Could not detect file type, defaulting to .bin (header: {header!r})")
        return '.bin'
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process file and extract packages.
        
        Args:
            file_path: Path to local file
        
        Returns:
            Result dict with status, packages, warnings, etc.
        """
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Extract packages using telecom service
            packages = self.extraction_service.process_document(file_path)
            
            warnings = []
            # Add warnings for missing fields
            for i, pkg in enumerate(packages, 1):
                if not pkg.get('name'):
                    warnings.append(f"Package {i}: missing name")
                if not pkg.get('partner_name'):
                    warnings.append(f"Package {i}: missing partner_name")
            
            result = {
                "status": "success",
                "content": {
                    "processed_at": datetime.utcnow().isoformat() + "Z",
                    "packages": packages,
                    "warnings": warnings,
                    "extracted_count": len(packages)
                }
            }
            
            logger.info(f"Extraction successful: {len(packages)} packages")
            return result
            
        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            return {
                "status": "error",
                "content": {
                    "error": str(e),
                    "processed_at": datetime.utcnow().isoformat() + "Z"
                }
            }
    
    def handle_import_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle import_file RPC method.
        
        Args:
            params: Request params with seaweed_file_id
        
        Returns:
            Result dict
        """
        seaweed_file_id = params.get('seaweed_file_id')
        if not seaweed_file_id:
            return {
                "status": "error",
                "content": {"error": "Missing seaweed_file_id"}
            }
        
        # Download file
        local_path = self.download_from_seaweed(seaweed_file_id)
        if not local_path:
            return {
                "status": "error",
                "content": {"error": f"Failed to download {seaweed_file_id}"}
            }
        
        try:
            # Process file
            result = self.process_file(local_path)
            return result
        finally:
            # Clean up temp file
            try:
                os.unlink(local_path)
            except:
                pass
    
    def on_request(self, ch, method, props, body):
        """
        RabbitMQ callback for incoming RPC requests.
        """
        try:
            # Parse request
            request = json.loads(body)
            request_id = request.get('id', 'unknown')
            rpc_method = request.get('method')
            params = request.get('params', {})
            
            logger.info(f"Received request {request_id}: {rpc_method}")
            
            # Handle method
            if rpc_method == 'import_file':
                result = self.handle_import_file(params)
            else:
                result = {
                    "status": "error",
                    "content": {"error": f"Unknown method: {rpc_method}"}
                }
            
            # Build response
            response = {
                "id": request_id,
                "result": result
            }
            
            # Send response back
            ch.basic_publish(
                exchange='',
                routing_key=self.response_queue,
                properties=pika.BasicProperties(
                    # correlation_id=props.correlation_id
                    delivery_mode=2  # make message persistent
                ),
                body=json.dumps(response, ensure_ascii=False)
            )
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            logger.info(f"Sent response for {request_id}: {result['status']}")
            
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            # Reject message
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def start(self):
        """Start listening to RabbitMQ queue."""
        self.connect_rabbitmq()
        
        # Set prefetch count
        self.channel.basic_qos(prefetch_count=1)
        
        # Start consuming
        self.channel.basic_consume(
            queue=self.request_queue,
            on_message_callback=self.on_request
        )
        
        logger.info(f"Waiting for import_file requests on queue: {self.request_queue}")
        logger.info("Press CTRL+C to exit")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping...")
            self.channel.stop_consuming()
        finally:
            if self.connection:
                self.connection.close()
                logger.info("Connection closed")


def main():
    """Main entry point."""
    # Load config from environment
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
    rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
    rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
    rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'guest')
    request_queue = os.getenv('FILE_IMPORT_REQUEST_QUEUE', 'file_import_requests')
    response_queue = os.getenv('FILE_IMPORT_RESPONSE_QUEUE', 'file_import_responses')
    seaweed_master = os.getenv('SEAWEED_MASTER', 'http://localhost:9333')
    model_name = os.getenv('LLM_MODEL', 'gpt-4o-mini')
    
    logger.info("Starting File Importing AI Agent (S15)")
    logger.info(f"RabbitMQ: {rabbitmq_host}:{rabbitmq_port}")
    logger.info(f"SeaweedFS: {seaweed_master}")
    logger.info(f"Model: {model_name}")
    
    agent = FileImportingAgent(
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_user=rabbitmq_user,
        rabbitmq_pass=rabbitmq_pass,
        request_queue=request_queue,
        response_queue=response_queue,
        seaweed_master=seaweed_master,
        model_name=model_name
    )
    
    agent.start()


if __name__ == '__main__':
    main()
