import os
import tempfile
import shutil
import ProcessLogger
from PdfProcessor import PDFProcessor
from s3_downloader import S3Downloader

class S3PdfProcessor:
    """
    Dedicated class for processing PDFs from S3 URLs
    """
    
    def __init__(self, s3_url, output_dir, language, config_parser):
        self.s3_url = s3_url
        self.output_dir = output_dir
        self.language = language
        self.config_parser = config_parser
        self.logger = ProcessLogger.getLogger('S3PdfProcessor')
        
    def process(self):
        """
        Main processing method: download S3 PDF, then process it
        """
        self.logger.info("Starting S3 PDF processing: %s", self.s3_url)
        
        # Download S3 PDF to temporary location
        s3_downloader = S3Downloader()
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Download S3 PDF
            local_pdf_path = s3_downloader.download_s3_pdf(self.s3_url, temp_dir)
            self.logger.info("Downloaded S3 PDF to: %s", local_pdf_path)
            
            # Initialize PdfProcessor with the downloaded local PDF
            pdf_processor = PDFProcessor(local_pdf_path, self.output_dir, self.language)
            pdf_processor.setConfigParser(self.config_parser)
            pdf_processor.writeStats()

            # Process the PDF
            if pdf_processor.isStructured():
                self.logger.info("Processing as structured PDF")
                pdf_processor.extractTextFromStructuredDoc()
            else:
                self.logger.info("Processing as scanned PDF with Textract")
                # Pass the original S3 URL for Textract processing
                pdf_processor.extractTextFromScannedDoc(self.s3_url)
            
            self.logger.info("S3 PDF processing completed successfully")
            
        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.logger.info("Cleaned up temporary download directory: %s", temp_dir)
