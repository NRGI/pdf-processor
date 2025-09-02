from os import listdir
import os.path
import json
from pdftools.PdfInfo import *
from pdftools.PdfToText import *
from pdftools.PdfTkSeparate import *
from pdftools.PdfSeparate import *
from textract.TextractPdfTextExtractor import *
import ProcessLogger

class PDFProcessor:
    logger = ProcessLogger.getLogger('PDFProcessor')
    
    def __init__(self, filePath, outputDir, language):
        self.filePath = filePath
        self.outputDir = outputDir
        self.language = language
        self.isEncrypted = False
        self.textContentSize = 0
        self.totalPages = 0
        self.process()
        self.processToCheckStructured()

    def setConfigParser(self, configParser):
        self.configParser = configParser

    def process(self):
        self.logger.info('Processing %s', self.filePath)
        self.logger.info('Calling Pdfinfo')
        pdfInfo = PdfInfo(self.filePath)
        self.totalPages = pdfInfo.getPages()
        self.fileSize = pdfInfo.getFileSizeInBytes()
        self.logger.info('Total Pages: %d, File Size: %d bytes', self.totalPages, self.fileSize)
        self.isEncrypted = pdfInfo.isEncrypted()
        if self.isEncrypted:
            self.writeStats()
            raise Exception('Pdf is encrypted. Can\'t do processing.')
        self.separatePdfPages()

    def processToCheckStructured(self):
        """
        dumps the entire pdf to text to get the size of the content
        """
        pdfToText = PdfToText(self.filePath, self.totalPages, self.outputDir)
        pdfToText.dumpPages()
        self.textContentSize += os.path.getsize(pdfToText.dumpedTextFilepath)
        self.logger.info('Text content size: %d bytes', self.textContentSize)
        self.logger.info('Structured? %s', self.isStructured())

    def isStructured(self):
        """
        assuming that text content should be at least 500 bytes in average in each page to say 
        that the pdf is structured
        """
        return True if self.textContentSize > (self.totalPages*500) else False

    def getStatus(self):
        if self.isEncrypted:
            return "Encrypted"
        else:
            return "Structured" if self.isStructured() else "Scanned";

    def writeStats(self):
        stats = {"pages": self.totalPages, "status": self.getStatus()}
        with open(os.path.join(self.outputDir,'stats.json'),'w') as outfile:
            json.dump(stats, outfile)
            self.logger.info('Writing %s to %s', json.dumps(stats), 'stats.json')

    def separatePdfPages(self):
        self.logger.info('Calling PdfTkseparate: Separating pdf to pages at %s', os.path.join(self.outputDir,'pages'))
        pdfTkSeparate = PdfTkSeparate(self.filePath, os.path.join(self.outputDir,'pages'))
        pdfTkProcessStatus = pdfTkSeparate.extractPages()
        self.logger.info('PdfTkseparate Status: %s', pdfTkProcessStatus)
        if pdfTkProcessStatus != 0:
            self.logger.info('Calling Pdfseparate: Separating pdf to pages at %s', os.path.join(self.outputDir,'pages'))
            pdfSeparate = PdfSeparate(self.filePath, os.path.join(self.outputDir,'pages'))
            pdfSeparate.extractPages()

    def extractTextFromStructuredDoc(self):
        """
        creates "text" dir to dump the extracted pages
        """
        self.logger.info('Calling Pdftotext: Dumping text pages at %s', os.path.join(self.outputDir,'text'))
        pdfToText = PdfToText(self.filePath, self.totalPages, os.path.join(self.outputDir,'text'))
        pdfToText.extractPages()

    def extractTextFromScannedDoc(self, s3_urls=None):
        """
        makes api calls to AWS Textract
        If s3_urls is provided, use S3 URLs directly. Otherwise, use local files.
        """
        self.logger.info('Calling Textract: OCR-ing %d pages at %s', self.totalPages, os.path.join(self.outputDir,'text'))
        textractPdf = TextractPdfTextExtractor(os.path.join(self.outputDir,'pages'), os.path.join(self.outputDir,'text'), self.totalPages, self.language)
        
        # AWS credentials will be automatically picked up from environment variables
        # No need to explicitly set them - the Textract client will use them automatically
        self.logger.info("Using AWS credentials from environment variables")
        
        if s3_urls:
            # Use S3 URLs directly
            textractPdf.extractPagesWithS3Urls(s3_urls)
        else:
            # Use local files (backward compatibility)
            textractPdf.extractPages();




