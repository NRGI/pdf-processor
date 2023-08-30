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
    ServerUrl = "http://cloud.ocrsdk.com/"
    # To create an application and obtain a password,
    # register at http://cloud.ocrsdk.com/Account/Register
    # More info on getting your application id and password at
    # http://ocrsdk.com/documentation/faq/#faq3
    ApplicationId = "user"
    Password = "password"
    Proxy = None
    enableDebugging = 0

    def ProcessImage(self, filePath, settings):
        url = "http://3.219.215.235/api/v1/Recognize/process"
        files = {'File': (os.path.basename(filePath), open(filePath, 'rb'), 'application/pdf')}
        data = {
            'RecognizeOptions.Language': settings.Language,
            'RecognizeOptions.AutoCropImage': True,
            'RecognizeOptions.AutoCorrectOrientation': True,
            'RecognizeOptions.Format': settings.OutputFormat,
            'RecognizeOptions.Barcodes': ''
        }
        headers = {'accept': 'application/octet-stream'}
        
        response = requests.post(url, files=files, data=data, headers=headers)
        
        if response.status_code != 200:
            self.logger.error(f'Error in API call: {response.status_code}')
            return None
        
        return response.content

    def GetTaskStatus(self, task):
        urlParams = urllib.parse.urlencode({"taskId": task.Id})
        statusUrl = self.ServerUrl + "getTaskStatus?" + urlParams
        headers = self.buildAuthHeader()
        response = requests.get(statusUrl, headers=headers)
        task = self.DecodeResponse(response.text)
        return task

    def DownloadResult(self, task, outputPath):
        getResultUrl = task.DownloadUrl
        if getResultUrl is None:
            print("No download URL found")
            return
        response = requests.get(getResultUrl)
        with open(outputPath, "wb") as resultFile:
            resultFile.write(response.content)

    def DecodeResponse(self, xmlResponse):
        """ Decode xml response of the server. Return Task object """
        dom = xml.dom.minidom.parseString(xmlResponse)
        taskNode = dom.getElementsByTagName("task")[0]
        task = Task()
        task.Id = taskNode.getAttribute("id")
        task.Status = taskNode.getAttribute("status")
        if task.Status == "Completed":
            task.DownloadUrl = taskNode.getAttribute("resultUrl")
        return task

    def buildAuthHeader(self):
        to_encode = f"{self.ApplicationId}:{self.Password}"
        base_encoded = base64.b64encode(to_encode.encode("iso-8859-1")).decode("utf-8")
        return {"Authorization": f"Basic {base_encoded}"}

