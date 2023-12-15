#!/usr/bin/env python3

# Usage: process.py <input file> <output file> [-language <Language>] [-pdf|-txt|-rtf|-docx|-xml]

import argparse
import base64
import os
import sys
import time
import urllib.parse
import requests
import xml.dom.minidom
import ProcessLogger

class ProcessingSettings:
    Language = "English"
    OutputFormat = "docx"

class Task:
    Status = "Unknown"
    Id = None
    DownloadUrl = None

    def IsActive(self):
        if self.Status == "InProgress" or self.Status == "Queued":
            return True
        else:
            return False

class AbbyyOnlineSdk:
    logger = ProcessLogger.getLogger('Abbyy_SDK')
    ServerUrl = None
    def __init__(self):
        base_url = os.environ.get('ABBYY_OCR_URL')
        if base_url:
            self.ServerUrl = base_url.rstrip('/') + '/api/v1/Recognize/process/'
            self.logger.info('ABBYY OCR URL NOT FOUND')
        else:
            self.ServerUrl = None
            self.logger.info(f'ABBY OCR URL IS: {self.ServerUrl}')

    ApplicationId = "user"
    Password = "password"
    Proxy = None
    enableDebugging = 0

    def ProcessImage(self, filePath, settings):
        try:
            files = {'File': (os.path.basename(filePath), open(filePath, 'rb'), 'application/pdf')}
        except IOError as e:
            self.logger.error(f'File error: {e}')
            return None

        data = {
            'RecognizeOptions.Language': settings.Language,
            'RecognizeOptions.AutoCropImage': True,
            'RecognizeOptions.AutoCorrectOrientation': True,
            'RecognizeOptions.Format': settings.OutputFormat,
            'RecognizeOptions.Barcodes': ''
        }
        headers = {'accept': 'application/octet-stream'}
        

        try:
            response = requests.post(self.ServerUrl, files=files, data=data, headers=headers, verify=False)
            response.raise_for_status()  # This will raise an HTTPError for non-200 status
            return response.content
        except requests.HTTPError as e:
            self.logger.error(f'HTTP error: {e.response.status_code} - {e.response.reason}')
        except requests.ConnectionError as e:
            self.logger.error(f'Connection error: {e}')
        except requests.Timeout as e:
            self.logger.error('Request timed out')
        except Exception as e:
            self.logger.error(f'Unexpected error: {e}')
        finally:
            files['File'][1].close()  # Ensure file is closed after the operation

        return None

