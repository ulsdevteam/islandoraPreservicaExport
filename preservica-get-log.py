import requests
import datetime
import time
import csv
import sys
import json
from urllib.parse import urljoin

'''
Copilot prompt:
Create a python script which, given a configuration file, queries a RESTful API to authenticate, then fetches paginated JSON responses to ultimately write out a CSV file.  The configuration file will include a username, password, and a base URL for the API endpoints.  The authentication endpoint is at "/api/accesstoken/login".  Provide an Accept header of "application/json", and POST the username and password as form urlencoded fields of username and password.  Check the JSON response for values of "success" (boolean), "token" (string), "refresh-token" (string), and "validFor" (integer, in minutes).  Use the token as the value for the header "Preservica-Access-Token" in subsequent requests, until it expires.  If expiry is less than 1 minute away, POST the "refresh-token" to the endpoint "/api/accesstoken/refresh", using the "Preservica-Access-Token" header, and reading a new "success" (boolean), "token" (string), "refresh-token" (string), and "validFor" (integer, in minutes).  For the paginated iteration, use the "Preservica-Access-Token" and "Accept: application/json;charset=UTF-8" in the headers for GET requests against the endpoint "/api/processmonitor/monitors" with querystring values of "status=Succeeded&category=Ingest&subcategory=OPEX".  Examine the JSON response for a value of "success" (boolean).  When success is true, examine the "value" key for a "paging" key which will contain a "totalResults" value (integer).  When pagination is needed, the "paging" key will also contain a "next" value with a URL to the subsequent page.  In the "value" key, a key called "monitors" will be an array of objects.  Each object will have a keys of "mappedId" (string) and "name" (string).  When "name" begins with "islandora", add the "mappedId" to an array which will be used in a separated paged call.  Harvest all "mappedId" values to that array, paginating and refreshing tokens as needed.  When the array is complete, use each "mappedId" as input to a GET request to the "/api/processmonitor/messages" endpoint.  Use the "Preservica-Access-Token" and "Accept: application/json;charset=UTF-8" headers, and supply the "mappedId" as the value of a "monitor" querystring parameter.  Also supply querystring parameters of "status=Info".  Again, examine the JSON response for a value of "success" (boolean).  When success is true, examine the "value" key for a "paging" key which will contain a "totalResults" value (integer).  When pagination is needed, the "paging" key will also contain a "next" value with a URL to the subsequent page.  In the "value" key, a key called "messages" will be an array of objects.  When the object in "messages" has a "sourceId" key which begins with "pitt:", write the value of the object's "sourceId" and "entityRef" values to STDOUT in CSV format.  Continue until pagination is exhausted.
'''

CONFIG_FILE = "preservica-config.json"  # Example: {"username": "...", "password": "...", "base_url": "https://example.com"}

# Load configuration
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

USERNAME = config["username"]
PASSWORD = config["password"]
BASE_URL = config["base_url"]

AUTH_ENDPOINT = "/api/accesstoken/login"
REFRESH_ENDPOINT = "/api/accesstoken/refresh"
MONITORS_ENDPOINT = "/api/processmonitor/monitors"
MESSAGES_ENDPOINT = "/api/processmonitor/messages"

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
        "Accept": "application/json;charset=UTF-8",
        "Preservica-Access-Token": token
    }

def fetch_paginated(url):
    """Fetch paginated results from given URL, yielding JSON 'value' objects."""
    while url:
        resp = requests.get(url, headers=get_headers())
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            break
        value = data.get("value", {})
        yield value
        paging = value.get("paging", {})
        url = paging.get("next")

def main():
    authenticate()

    # Step 1: Collect mappedIds from monitors
    monitors_url = urljoin(BASE_URL, MONITORS_ENDPOINT) + "?status=Succeeded&category=Ingest&subcategory=OPEX"
    # If an argument is supplied in YYYY-MM-DD format, we'll treat this as the starting date, UTC
    # This will also fetch the logs in date order
    if len(sys.argv) > 1 and sys.argv[1]:
        begin = None
        try:
            begin = datetime.datetime.strptime(sys.argv[1], '%Y-%m-%d')
        except Exception as e:
            print(e, file=sys.stderr)
            print('Ignoring ' + sys.argv[1], file=sys.stderr)
        if begin:
            monitors_url += '&startedFrom=' + begin.isoformat() + '.000Z&sort=StartDate+ASC'
    mapped_ids = []
    for value in fetch_paginated(monitors_url):
        for monitor in value.get("monitors", []):
            if monitor.get("name", "").startswith("islandora"):
                mapped_ids.append(monitor["mappedId"])

    # Step 2: For each mappedId, fetch messages and output CSV
    writer = csv.writer(sys.stdout)
    writer.writerow(["sourceId", "entityRef"])
    for mid in mapped_ids:
        messages_url = urljoin(BASE_URL, MESSAGES_ENDPOINT) + f"?monitor={mid}&status=Info"
        for value in fetch_paginated(messages_url):
            for msg in value.get("messages", []):
                source_id = msg.get("sourceId", "")
                if source_id.startswith("pitt:"):
                    writer.writerow([source_id, msg.get("entityRef", "")])

if __name__ == "__main__":
    main()

