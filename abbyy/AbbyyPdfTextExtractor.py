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
        infile = os.path.join(self.indir, f"{page}.pdf")
        outfile = os.path.join(self.outdir, f"{page}.txt")
        settings = ProcessingSettings()
        settings.Language = self.language
        settings.OutputFormat = self.outputFormat
        self.logger.info(f'Processing {infile}')

        try:
            response_content = self.processor.ProcessImage(infile, settings)
            if response_content is None:
                self.logger.error(f'Error in processing {infile} - No content returned')
                return

            with open(outfile, 'wb') as op:
                op.write(response_content)
            self.logger.info(f'Result written to {outfile}')
        
        except IOError as e:
            self.logger.error(f'File I/O error: {e}')
        except requests.RequestException as e:
            self.logger.error(f'Network error during processing: {e}')
        except Exception as e:
            self.logger.error(f'Unexpected error: {e}')


    def extractPages(self):
        for page in range(1, self.pages + 1):
            self.processPdfPage(page)
            outputFileName = os.path.join(self.outdir, str(page) + ".txt")

            try:
                if os.path.exists(outputFileName):
                    with open(outputFileName, 'r') as infile:
                        content = infile.read()
                    with open(outputFileName, 'w') as outfile:
                        outfile.write(self.nl2br(content))
                else:
                    self.logger.error(f'Output file {outputFileName} not found.')
            except IOError as e:
                self.logger.error(f'Error reading/writing file: {e}')


    def nl2br(self, s):
        return '<br />\n'.join(s.split('\n'))

