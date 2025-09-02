import argparse
import os
import sys
from datetime import datetime
import configparser
import ProcessLogger
import traceback
from urllib.request import URLError, HTTPError
from PdfProcessor import PDFProcessor
import json

parser = argparse.ArgumentParser(description='Processes the pdf and extracts the text')
parser.add_argument('-l', '--language', help='Language of input pdf file for transcription (english, french, spanish).', required=False, default="english")
parser.add_argument('-i', '--infile', help='File path of the input pdf file or S3 URL (s3://bucket/key).', required=True)
parser.add_argument('-o', '--outdir', help='File name of the output csv file.', required=True)
results = parser.parse_args()
allowed_languages = ["english", "french", "spanish", "portuguese", "arabic"]
pdfProcessor = ""

try:
    logger = ProcessLogger.getLogger('run')
    logger.info("Processing started at %s ", str(datetime.now()))
    logger.info("input: %s", results.infile)
    logger.info("outdir: %s", results.outdir)
    language = results.language.lower()
    if language not in allowed_languages:
        raise Exception("language should be one of english, french, spanish, portuguese or arabic")

    if language == "portuguese":
        language = "portuguesestandard"
    
    if language != "english":
        language += ",english"

    # Create config parser for backward compatibility
    configParser = configparser.RawConfigParser()
    configParser.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.config'))

    # Check if input is S3 URL
    if results.infile.startswith('s3://'):
        # Handle S3 URL directly with Textract
        logger.info("Processing S3 URL: %s", results.infile)
        
        # Create output directory structure to match original implementation
        pages_dir = os.path.join(results.outdir, 'pages')
        text_dir = os.path.join(results.outdir, 'text')
        
        if not os.path.exists(pages_dir):
            os.makedirs(pages_dir)
        if not os.path.exists(text_dir):
            os.makedirs(text_dir)
        
        # For S3 URLs, we'll use Textract directly
        from textract.TextractPdfTextExtractor import TextractPdfTextExtractor
        textractPdf = TextractPdfTextExtractor(pages_dir, text_dir, 1, language)
        
        # AWS credentials will be automatically picked up from environment variables
        logger.info("Using AWS credentials from environment variables")
        
        # Process S3 URL directly
        textractPdf.extractPagesWithS3Urls([results.infile])
        
        # Check if output files were created in the correct structure
        expected_text_file = os.path.join(text_dir, '1.txt')
        if os.path.exists(expected_text_file):
            logger.info(f"Textract output created: {expected_text_file}")
        else:
            logger.warning(f"Expected text file not found: {expected_text_file}")
            # List what's in the text directory
            if os.path.exists(text_dir):
                files = os.listdir(text_dir)
                logger.info(f"Files in text directory: {files}")
        
        # Generate dynamic stats based on actual files created for S3 URLs
        stats = textractPdf.generate_stats(results.infile, language, 1)
        
        with open(os.path.join(results.outdir, 'stats.json'), 'w') as f:
            json.dump(stats, f, indent=2)
        logger.info("Dynamic stats generated: %s", json.dumps(stats))
        logger.info("S3 processing completed successfully")
    else:
        # Handle local file as before
        pdfProcessor = PDFProcessor(results.infile, results.outdir, language)
        pdfProcessor.setConfigParser(configParser)
        pdfProcessor.writeStats()

        if pdfProcessor.isStructured():
            pdfProcessor.extractTextFromStructuredDoc()
        else:
            pdfProcessor.extractTextFromScannedDoc()

except URLError as e:
    logger.error("URLError: %s", e.reason)
    logger.debug(traceback.format_exception(*sys.exc_info()))

except HTTPError as e:
    logger.error("HTTPError: [%s] %s", e.code, e.reason)
    logger.debug(traceback.format_exception(*sys.exc_info()))

except OSError as e:
    logger.error("OSError: %s [%s] in %s", e.strerror, e.errno, e.filename)
    logger.debug(traceback.format_exception(*sys.exc_info()))

except Exception as e:
    logger.error("Exception: %s ", e)
    logger.debug(traceback.format_exception(*sys.exc_info()))

finally:
    logger.info("Processing ended at %s ", str(datetime.now()))
