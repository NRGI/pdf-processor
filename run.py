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
        # Handle S3 URL using dedicated S3 processor
        from s3_pdf_processor import S3PdfProcessor
        s3_processor = S3PdfProcessor(results.infile, results.outdir, language, configParser)
        s3_processor.process()
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
