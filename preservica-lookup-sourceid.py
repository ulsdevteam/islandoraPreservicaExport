import requests
import time
import csv
import sys
import json
import xml.etree.ElementTree
import io
from urllib.parse import urljoin, quote
"""
Given STDIN input of a CSV which has columns of (1) an Islandora PID (`sourceId`)
Check Preservica for objects with that same Islandora PID in the sourceId
STDOUT will be a CSV of sourceId (input) and entityId (matching object)
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

def parse_with_ns(xml_text):
    """
    Parse XML text while capturing all declared namespaces.
    Returns (root_element, {prefix: uri, ...})
    """
    namespaces = {}
    root = None

    # iterparse needs a file-like object; wrap the string
    for event, value in xml.etree.ElementTree.iterparse(io.StringIO(xml_text), events=("start-ns", "end")):
        if event == "start-ns":
            prefix, uri = value
            namespaces[prefix] = uri
        elif event == "end":
            root = value  # the last "end" event is always the root element

    return root, namespaces

def find_namespace_by_prefix(namespaces, prefix):
    """
    Return the first namespace URI that starts with the given prefix string.
    """
    for uri in namespaces.values():
        if uri.startswith(prefix):
            return uri
    raise ValueError(f"No namespace found starting with {prefix!r}")

def main():
    authenticate()

    reader = csv.DictReader(sys.stdin)
    writer = csv.DictWriter(sys.stdout, ['sourceId', 'entityId'])
    writer.writeheader()
    for row in reader:
        # get all existing matches for the sourceId
        escaped_pid = quote(row['sourceId'])
        lookup_url = urljoin(BASE_URL, LOOKUP_ENDPOINT) + f"?type=SourceId&value={escaped_pid}"
        resp = requests.get(lookup_url, headers=get_headers())
        resp.raise_for_status()
        data, ns = parse_with_ns(resp.text)
        versioned_ns = find_namespace_by_prefix(ns, 'http://preservica.com/EntityAPI/v')
        matches =[]
        for entity in data.findall(f'.//{{{versioned_ns}}}Entities/{{{versioned_ns}}}Entity'):
            matches.append(entity.attrib['ref'])
        if matches:
            line = { 'sourceId': row['sourceId'], 'entityId': ','.join(matches) }
            writer.writerow(line)

if __name__ == "__main__":
    main()

