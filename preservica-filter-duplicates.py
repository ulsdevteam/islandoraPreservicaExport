import requests
import time
import csv
import sys
import json
import xml.etree.ElementTree
from urllib.parse import urljoin, quote
"""
Somehow we are still getting duplicate ingests for Islandora 7 content.  This script will filter output from a
Preservica process log (c.f. preservica-get-log.py) to abort the processing of duplicated objects, and to
allow unduplicated object ids to be passed along to preserica-mark-ingested.sh.

Given STDIN input of a CSV which has columns of (1) an Islandora PID, and (2) a Preservica entityId
Check Preservica for other instances of objects with that same Islandora PID in the sourceId
If other instances are found, notice of these duplicates and siblings will be written to STDERR
if the parameter "move" is present,  move the new Preservica entity and any immediate siblings to a Trash folder
STDOUT will be a filtered version of the CSV input where no duplicate was detected.
"""

CONFIG_FILE = "preservica-config.json"  # Example: {"username": "...", "password": "...", "base_url": "https://example.com"}

# Load configuration
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

USERNAME = config["username"]
PASSWORD = config["password"]
BASE_URL = config["base_url"]
TRASH_REF = config['trash_ref']

AUTH_ENDPOINT = "/api/accesstoken/login"
REFRESH_ENDPOINT = "/api/accesstoken/refresh"
LOOKUP_ENDPOINT = "/api/entity/entities/by-identifier"
IO_ENDPOINT = "/api/entity/information-objects"
SEARCH_ENDPOINT = "/api/content/search"

# Globals for token management
token = None
refresh_token = None
expiry_time = None  # epoch timestamp when token expires

def authenticate():
    global token, refresh_token, expiry_time
    url = urljoin(BASE_URL, AUTH_ENDPOINT)
    headers = {"Accept": "application/json"}
    data = {"username": USERNAME, "password": PASSWORD}
    resp = requests.post(url, headers=headers, data=data)
    resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise Exception("Authentication failed")
    token = result["token"]
    refresh_token = result["refresh-token"]
    expiry_time = time.time() + (result["validFor"] * 60)

def refresh():
    global token, refresh_token, expiry_time
    url = urljoin(BASE_URL, REFRESH_ENDPOINT) + f"?refreshToken={refresh_token}"
    headers = {
        "Accept": "application/json",
        "Preservica-Access-Token": token
    }
    resp = requests.post(url, headers=headers)
    resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise Exception("Token refresh failed")
    token = result["token"]
    refresh_token = result["refresh-token"]
    expiry_time = time.time() + (result["validFor"] * 60)

def ensure_token_valid():
    if expiry_time - time.time() < 60:  # less than 1 minute left
        refresh()

def get_headers():
    ensure_token_valid()
    return {
        "Preservica-Access-Token": token
    }

def main():
    authenticate()

    reader = csv.DictReader(sys.stdin)
    out = []
    for row in reader:
        # Get the name and parent for the new entity
        get_url = urljoin(BASE_URL, IO_ENDPOINT) + f"/{row['entityId']}"
        resp = requests.get(get_url, headers=get_headers())
        resp.raise_for_status()
        data = xml.etree.ElementTree.fromstring(resp.text)
        name = data.find('.//{http://preservica.com/XIP/v8.3}InformationObject/{http://preservica.com/XIP/v8.3}Title').text
        parent = data.find('.//{http://preservica.com/XIP/v8.3}InformationObject/{http://preservica.com/XIP/v8.3}Parent').text
        # get all existing matches for the sourceId
        escaped_pid = quote(row['sourceId'])
        lookup_url = urljoin(BASE_URL, LOOKUP_ENDPOINT) + f"?type=SourceId&value={escaped_pid}"
        resp = requests.get(lookup_url, headers=get_headers())
        resp.raise_for_status()
        data = xml.etree.ElementTree.fromstring(resp.text)
        existing = None
        duplicateIds = []
        for entity in data.findall('.//{http://preservica.com/EntityAPI/v8.3}Entities/{http://preservica.com/EntityAPI/v8.3}Entity'):
            if entity.attrib['ref'] != row['entityId']:
                existing = entity.attrib['ref']
        # find all sibings of the new entity with the same name stem
        if existing:
            query = {
                "q": name + "*",
                "fields": [
                    {
                        "name": "xip.title",
                        "values": [ name + '*' ]
                    },
                    {
                        "name": "xip.parent_ref",
                        "values": [ parent ]
                    }
                ]
            }
            search_url = urljoin(BASE_URL, SEARCH_ENDPOINT) + f'?start=0&max=100&metadata=id&q=' + quote(json.dumps(query))
            resp = requests.get(search_url, headers=get_headers())
            resp.raise_for_status()
            data = resp.json()
            for entityId in data['value']['objectIds']:
                entityRef = entityId.replace('sdb:IO|', '')
                duplicateIds.append(entityRef) 
            print(row['sourceId'] + ',' + existing + ',"' + ','.join(duplicateIds) + '"', file=sys.stderr)
            if len(sys.argv) > 1 and sys.argv[1] == 'move':
                for entityRef in duplicateIds:
                    move_url = urljoin(BASE_URL, IO_ENDPOINT) + f'/{entityRef}/parent-ref'
                    resp = requests.put(move_url, headers=get_headers(), data={ 'ref': TRASH_REF })
                    resp.raise_for_status()
        else:
            out.append(row)
    if out:
        writer = csv.DictWriter(sys.stdout, reader.fieldnames)
        writer.writeheader()
        writer.writerows(out)

if __name__ == "__main__":
    main()

