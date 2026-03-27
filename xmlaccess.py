import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from datetime import date, datetime
import sys
import os


#script to access DC.XML file and find the collection number and return it

#get DC.xml file as an argument

if len(sys.argv) != 2 or sys.argv[1].endswith(".xml") is False:
    print("parameter error")
    sys.exit(1)
else:
    DcFile = (sys.argv[1])

collection = ''
tree = ET.parse(DcFile)
root = ET.parse(DcFile).getroot()

for child in root:
    if child.text.startswith("pitt:collection.") or child.text.startswith("pitt: collection."):
        collection = ((child.text.split('.',1))[1])

if collection != '':
    print(collection)
    sys.exit(0)
else:
    sys.exit(1)