"""
SeaweedFS Client for uploading and retrieving files.

This client provides simple methods to interact with SeaweedFS's HTTP API.
"""
import requests
import urllib.parse
from requests import exceptions as req_exceptions
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SeaweedFSClient:
    """
    Client for interacting with SeaweedFS file storage.
    
    SeaweedFS API workflow:
    1. Request file assignment from master server (GET /dir/assign)
    2. Upload file to assigned volume server (POST to returned url)
    3. Access file using fid (GET http://volume_server:port/fid)
    """
    
    def __init__(self, master_url: str = "http://localhost:9333", volume_url: Optional[str] = None):
        """
        Initialize SeaweedFS client.
        
        Args:
            master_url: URL of SeaweedFS master server (default: http://localhost:9333)
            volume_url: Optional specific volume server URL. If not provided,
                       will use the volume server returned by master during assignment.
        """
        self.master_url = master_url.rstrip('/')
        self.volume_url = volume_url.rstrip('/') if volume_url else None
        logger.info(f"SeaweedFS client initialized with master: {self.master_url}")
    
    def assign_file_id(self) -> Tuple[str, str]:
        """
        Request a file ID assignment from the master server.
        
        Returns:
            Tuple of (fid, public_url) where:
                - fid: The assigned file ID (e.g., "3,01637037d6")
                - public_url: The public URL to upload to (e.g., "http://localhost:8080/3,01637037d6")
        
        Raises:
            requests.RequestException: If the request fails
            ValueError: If the response is invalid
        """
        assign_url = f"{self.master_url}/dir/assign"
        logger.debug(f"Requesting file ID assignment from {assign_url}")
        
        response = requests.get(assign_url, timeout=10)
        response.raise_for_status()

        data = response.json()
        if 'fid' not in data or ('url' not in data and 'publicUrl' not in data):
            raise ValueError(f"Invalid assignment response: {data}")

        fid = data['fid']
        # Determine upload URL preference: explicit volume_url override -> publicUrl -> url
        if self.volume_url:
            # caller provided an explicit volume URL
            public_url = f"{self.volume_url.rstrip('/')}/{fid}"
        else:
            # prefer publicUrl when available (it should be reachable from host)
            volume_location = data.get('publicUrl') or data.get('url')
            # If volume_location already contains a scheme, use it; otherwise prefix http://
            if volume_location.startswith('http://') or volume_location.startswith('https://'):
                public_url = f"{volume_location.rstrip('/')}/{fid}"
            else:
                public_url = f"http://{volume_location}/{fid}"
        
        logger.info(f"Assigned file ID: {fid}, upload URL: {public_url}")
        return fid, public_url
    
    def upload_file(self, file_path: str, filename: Optional[str] = None) -> Tuple[str, str]:
        """
        Upload a file to SeaweedFS.
        
        Args:
            file_path: Path to the file to upload
        
        Returns:
            Tuple of (fid, public_url) where:
                - fid: The file ID that can be used to retrieve the file
                - public_url: The full URL to access the file
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            requests.RequestException: If upload fails
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Step 1: Get file ID assignment
        fid, upload_url = self.assign_file_id()
        
        # Step 2: Upload the file
        logger.info(f"Uploading {file_path.name} to {upload_url}")
        
        # Use provided filename for the uploaded filename if given
        upload_filename = filename or file_path.name
        with open(file_path, 'rb') as f:
            files = {'file': (upload_filename, f)}
            response = requests.post(upload_url, files=files, timeout=30)
            response.raise_for_status()
        
        upload_result = response.json()
        logger.info(f"Upload successful: {upload_result}")
        
        # Return the fid and the URL to access it
        return fid, upload_url
    
    def download_file(self, fid: str) -> Tuple[bytes, dict]:
        """
        Download a file from SeaweedFS by its file ID.
        
        Args:
            fid: The file ID (e.g., "3,01637037d6")
        
        Returns:
            Tuple of (content bytes, response headers dict)
        
        Raises:
            requests.RequestException: If download fails
        """
        # First try to use explicit volume_url if provided
        tried_urls = []
        if self.volume_url:
            download_url = f"{self.volume_url.rstrip('/')}/{fid}"
            tried_urls.append(download_url)
        else:
            # Look up the file location from master
            lookup_url = f"{self.master_url}/dir/lookup?volumeId={fid.split(',')[0]}"
            logger.debug(f"Looking up file location: {lookup_url}")

            response = requests.get(lookup_url, timeout=10)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Lookup response: {data}")
            if 'locations' not in data or not data['locations']:
                raise ValueError(f"No location found for file ID: {fid}")

            # Use the first available location and prefer publicUrl
            location = data['locations'][0]
            volume_location = location.get('publicUrl') or location.get('url')

            # Build primary download URL
            if volume_location.startswith('http://') or volume_location.startswith('https://'):
                download_url = f"{volume_location.rstrip('/')}/{fid}"
            else:
                download_url = f"http://{volume_location}/{fid}"
            tried_urls.append(download_url)

        logger.info(f"Attempting to download file; tried URLs: {tried_urls}")

        # Try primary download URL, then reasonable fallbacks for Docker setups
        last_exc = None
        try_urls = list(tried_urls)

        # If the primary url appears to be a Docker-internal IP, add fallback to localhost:8080
        primary_host = None
        try:
            parsed = urllib.parse.urlparse(try_urls[0])
            primary_host = parsed.hostname
        except Exception:
            primary_host = None

        if primary_host and (primary_host.startswith('172.') or primary_host.startswith('10.') or primary_host == '127.0.0.1'):
            # add localhost fallback
            try_urls.append(f"http://localhost:8080/{fid}")
            # also try master host with default volume port
            try:
                master_parsed = urllib.parse.urlparse(self.master_url)
                master_host = master_parsed.hostname or 'localhost'
                try_urls.append(f"http://{master_host}:8080/{fid}")
            except Exception:
                pass

        for url in try_urls:
            logger.info(f"Downloading file from {url}")
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                return resp.content, dict(resp.headers)
            except req_exceptions.RequestException as e:
                logger.warning(f"Failed to download from {url}: {e}")
                last_exc = e

        # All attempts failed
        raise last_exc or RuntimeError(f"Failed to download file {fid}")
    
    def delete_file(self, fid: str) -> bool:
        """
        Delete a file from SeaweedFS.
        
        Args:
            fid: The file ID to delete
        
        Returns:
            True if deletion was successful
        
        Raises:
            requests.RequestException: If deletion fails
        """
        if self.volume_url:
            delete_url = f"{self.volume_url}/{fid}"
        else:
            # Look up volume location first
            lookup_url = f"{self.master_url}/dir/lookup?volumeId={fid.split(',')[0]}"
            response = requests.get(lookup_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'locations' not in data or not data['locations']:
                raise ValueError(f"No location found for file ID: {fid}")
            
            location = data['locations'][0]
            volume_url = location.get('url') or location.get('publicUrl')
            delete_url = f"http://{volume_url}/{fid}"
        
        logger.info(f"Deleting file: {delete_url}")
        response = requests.delete(delete_url, timeout=10)
        response.raise_for_status()
        
        return True


# Convenience function for quick uploads
def upload(file_path: str, master_url: str = "http://localhost:9333") -> Tuple[str, str]:
    """
    Convenience function to upload a file to SeaweedFS.
    
    Args:
        file_path: Path to file to upload
        master_url: SeaweedFS master server URL
    
    Returns:
        Tuple of (fid, public_url)
    """
    client = SeaweedFSClient(master_url=master_url)
    return client.upload_file(file_path)
