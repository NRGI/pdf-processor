from abbyy.AbbyyOnlineSdk import *
import ProcessLogger

class AbbyyPdfTextExtractor:
    logger = ProcessLogger.getLogger('Abbyy')

    def __init__(self, indir, outdir, pages, language):
        self.processor = AbbyyOnlineSdk()
        self.processor.ApplicationId = ""
        self.processor.Password = ""
        self.outputFormat = 'txt'
        self.language = language
        self.indir = indir
        self.pages = pages
        self.outdir = outdir
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)        

    def setApplicationCredentials(self, appid, password):
        self.processor.ApplicationId = appid
        self.processor.Password = password
    
    def processPdfPage(self, page):
        """
        all the pdf in outdir are named as 1.pdf, 2.pdf based on the page numbers
        """
        infile = os.path.join(self.indir, f"{page}.pdf")
        outfile = os.path.join(self.outdir, f"{page}.txt")
        settings = ProcessingSettings()
        settings.Language = self.language
        settings.OutputFormat = self.outputFormat
        self.logger.info(f'Processing {infile}')
        response_content = self.processor.ProcessImage(infile, settings)
        
        if response_content is None:
            self.logger.error(f'Error in processing {infile}')
            return
        
        # Write the returned content to the output directory
        with open(outfile, 'wb') as op:
            op.write(response_content)
        
        self.logger.info(f'Result written to {outfile}')

    def extractPages(self):
        for page in range(1, self.pages+1):
            self.processPdfPage(page)
            outputFileName = os.path.join(self.outdir, str(page) + ".txt")
            with open(outputFileName, 'r') as infile:
                content = infile.read()    
            with open(outputFileName, 'w') as outfile:
                outfile.write(self.nl2br(content))

    def nl2br(self, s):
        return '<br />\n'.join(s.split('\n'))

