import subprocess
import logging

"""
ideas from https://gist.github.com/godber/7692812
"""

class PdfInfo:
    def __init__(self, filepath):
        self.filepath = filepath
        self.info = {}
        self.cmd = "pdfinfo"
        self.logger = logging.getLogger('PdfInfo')
        self.process()

    def process(self):
        labels = ['Title', 'Author', 'Creator', 'Producer', 'CreationDate', \
                'ModDate', 'Tagged', 'Pages', 'Encrypted', 'Page size', \
                'File size', 'Optimized', 'PDF version']      
        
        # Try multiple encoding strategies in order of preference
        encodings_to_try = [
            ('utf-8', 'replace'),      # UTF-8 with replacement for invalid chars
            ('utf-8', 'ignore'),       # UTF-8 ignoring invalid chars
            ('latin-1', 'strict'),     # Latin-1 (can handle any byte value)
            ('cp1252', 'replace'),     # Windows-1252 with replacement
            ('iso-8859-1', 'strict')   # ISO-8859-1 (same as latin-1)
        ]
        
        cmdOutput = None
        encoding_used = None
        
        for encoding, errors in encodings_to_try:
            try:
                cmdOutput = subprocess.check_output(
                    [self.cmd, self.filepath], 
                    text=True, 
                    encoding=encoding,
                    errors=errors,
                    stderr=subprocess.DEVNULL  # Suppress stderr to avoid noise
                )
                encoding_used = f"{encoding} with {errors}"
                break
            except (UnicodeDecodeError, subprocess.CalledProcessError) as e:
                self.logger.debug(f"Failed with encoding {encoding}/{errors}: {e}")
                continue
        
        if cmdOutput is None:
            raise Exception(f"Failed to execute {self.cmd} on {self.filepath} with any encoding")
        
        if encoding_used != "utf-8 with replace":
            self.logger.warning(f"Used fallback encoding: {encoding_used} for {self.filepath}")
        
        for line in cmdOutput.splitlines():
            for label in labels:
                if label in line:
                    self.info[label] = self.extract(line)
    
    def isEncrypted(self):
        return False if (self.info['Encrypted'][:2]=="no") else True

    def extract(self, row):
        return row.split(':', 1)[1].strip()

    def getPages(self):
        return int(self.info['Pages'])

    def getFileSizeInBytes(self):
        return int(self.info['File size'][:-5].strip())

