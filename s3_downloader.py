import os
import tempfile
import boto3
from urllib.parse import urlparse
import ProcessLogger

class S3Downloader:
    """
    Service to download S3 files to local storage
    """
    logger = ProcessLogger.getLogger('S3Downloader')
    
    def __init__(self):
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
    
    def download_s3_pdf(self, s3_url, output_dir):
        """
        Download S3 PDF to local file and return the local file path
        
        Args:
            s3_url (str): S3 URL (e.g., s3://bucket/path/file.pdf)
            output_dir (str): Directory to save the downloaded file
            
        Returns:
            str: Local file path of the downloaded PDF
        """
        # Extract bucket and key from S3 URL using proper URL parsing
        parsed_url = urlparse(s3_url)
        bucket_name = parsed_url.netloc
        s3_key = parsed_url.path.lstrip('/')  # Remove leading slash
        
        # Validate that we have both bucket and key
        if not bucket_name:
            raise ValueError(f"Invalid S3 URL: missing bucket name in {s3_url}")
        if not s3_key:
            raise ValueError(f"Invalid S3 URL: missing file key in {s3_url}")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Generate local file path
        filename = os.path.basename(s3_key)
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        local_file_path = os.path.join(output_dir, filename)
        
        # Download the file
        self.logger.info(f"Downloading S3 PDF: {s3_url}")
        self.logger.info(f"Bucket: {bucket_name}, Key: {s3_key}")
        self.logger.info(f"Local path: {local_file_path}")
        
        try:
            self.s3_client.download_file(bucket_name, s3_key, local_file_path)
            self.logger.info(f"Successfully downloaded PDF to: {local_file_path}")
            return local_file_path
        except Exception as e:
            self.logger.error(f"Failed to download S3 PDF: {e}")
            raise
