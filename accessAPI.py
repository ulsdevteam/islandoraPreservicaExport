import json
import requests
import xml.etree.ElementTree as ET
import sys
import csv
import logging
import subprocess

#parent ref arg 1
# refs to move.refs arg 2

logging.basicConfig(
    level=logging.ERROR,
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('errors.log', mode='a')
    ]
)


if len(sys.argv) < 2: 
    print('usage: python3 accessAPI.py <deduplicated file> ')
    sys.exit(1)
else: print(f"file to use: {sys.argv[1]}")


def login():
    url = "https://pitt.preservica.com/api/accesstoken/login"

    data = {
    "username": "",
    "password": "",
    "tenant": "pitt"
    }

    response = requests.post(url, data=data)
    if response.status_code == 200: json_response = response.json() 
    else: 
        err_msg = f"login failed with status code {response.status_code}"
        logging.error(err_msg)
        sys.exit(1)
    
    access_token = json_response['token']
    return access_token


# SO_id = 'a18e4ca8-0ea9-4923-a8cc-92f00f437fcd'
# count = 0
# max_items = 500
#endpoint_url = f"https://pitt.preservica.com/api/entity/structural-objects/{SO_id}/children?ref={SO_id}&start={count}&max={max_items}"


# structural object = folders
# information object = assets

# ref = '7f026b8c-8e8a-43c6-9f99-e66adac826f0'
# move_info_url = f"https://pitt.preservica.com/api/entity/information-objects/{ref}/parent-ref"
# move_struct_url = f"https://pitt.preservica.com/api/entity/structural-objects/{SO_id}/parent-ref"

# headers = {
#     "Authorization": f"Bearer {access_token}",
#     "Content-Type": "text/plain",
# }

#z_trash folder
# newParentRef = 'a1b1a897-60df-4ebf-88df-6020554a48e8'

# ref_csv = 'refs-to-move.csv'
ref = '6f2f3c98-db1d-4a5a-9a37-8d2619d4485a'
# ref = '238e1af7-074b-41cf-91f1-66aec11c71fc'
identifier_url = f"https://pitt.preservica.com/api/entity/information-objects/{ref}/identifiers"
search_url = "https://pitt.preservica.com/api/content/search"

islandora_ingest_ref = ['54346d6b-e9ec-4cc1-a102-63fb68ac9177']

# response = requests.get(identifier_url, headers=headers)
# if response.status_code in {403,404,422} or response.status_code != 200: 
#     err_msg = f"{ref} trouble getting with status code {response.status_code}"
#     logging.error(err_msg)
# else: print(f"successfully returned response")
# root = ET.fromstring(response.text)
# namespace = {'xip': 'http://preservica.com/XIP/v7.5'}
# value = root.find('.//xip:Value', namespace)

def move_to_trash(csvFile, token):

    parentRef = 'a1b1a897-60df-4ebf-88df-6020554a48e8'
    headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "text/plain",
    }

    with open(csvFile, 'r') as file:
        for line in file:
            ref = line.strip()
            move_url = f"https://pitt.preservica.com/api/entity/information-objects/{ref}/parent-ref"
            response = requests.put(move_url, headers=headers, data=parentRef)
            if response.status_code in {403,404,422} or response.status_code != 202: 
                err_msg = f"{ref} trouble moving with status code {response.status_code}"
                logging.error(err_msg)
            else: print(f"successfully started {ref} move to {parentRef}")


def run_query(sourceID, gameraRef, token):

    headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "text/plain",
    }

    query = {
    "q": "",
    "fields": [
        {
            "name": "xip.identifier",
            "values": [sourceID]
        }
        # ,
        # {
        #     "name": "xip:type",
        #     "values": "Asset"
        # }
    ],
  }
    q = json.dumps(query)

    data = {
    "q": q,
    "start": 0,
    "max": 10,
    "metadata": "xip.title,xip.parent_ref,xip.identifier,xip.top_level_so"
    }

    search_url = "https://pitt.preservica.com/api/content/search"
    response = requests.post(search_url, headers=headers, params=data)

    # Check if the request was successful
    if response.status_code == 200: print("success")
    else: print(f"Error: {response.status_code}, {response.text}")

    #parse json
    response_json = response.json()
    total_hits = int(response_json["value"]["totalHits"])

    if total_hits == 0:
        print("no preservica refs attached to this SourceID")
        return
    else: print(f"total hits: {total_hits}")

    object_refs = {}
    #list of refs and top folder refs
    object_ids = [item.split("|")[1] for item in response_json["value"]["objectIds"]]
    metadata = response_json["value"]["metadata"]

    object_refs = dict.fromkeys(object_ids, bool(False))
    for ref in object_refs:
        print(f"object ref: {ref} tagged as {object_refs[ref]}")
    # only_ref = (object_ids[0].split("|"))[1]
    # print(f"only the ref: {only_ref}")
    # print(metadata)

    top_level_dict = {}
    flagged = bool(False)
    authoritative_refs = {}
    islandora_ingest_ref = ['54346d6b-e9ec-4cc1-a102-63fb68ac9177']

    for i, obj_id in enumerate(object_ids):
        for data in metadata[i]:
            if data["name"] == "xip.top_level_so": 
                top_level_dict[obj_id] = data["value"]

    for obj_id in top_level_dict: 
        print(f"object id: {obj_id} and the top level so: {top_level_dict[obj_id]}")
        if (top_level_dict[obj_id] == islandora_ingest_ref): print("top level is islandora ingest")
        else: 
            print("top level not islandora ingest")
            if flagged == False:
                # add ref as authoriative
                print("adding as authoritative")
                object_refs[obj_id] = bool(True)
                authoritative_refs[obj_id] = top_level_dict[obj_id]
                flagged = True
            else:
                # raise an error because multiple are authoritative
                print("multiple flagged as authoritative error")
                return
        
    #out of the for loop for the multiple refs
    if flagged == False:
        print(f"last item ref: {object_ids[-1]}")
        object_refs[object_ids[-1]] = bool(True)

    #for each ref
    for ref in object_refs:
        # if ref is flagged
        if object_refs[ref] == True:
            # drush command to pull islandora ref
            #if ref differs then update in gamera
            print(f"checking gamera for {ref}")
            if ( ref == gameraRef ): print(f"{ref} same as {gameraRef}")
            else: print(f"use drush to update the preservica ref to {ref}")
        else:
            # move ref to trash folder
            # file = open("move-to-trash.csv", "a")
            # file.write(ref)
            print(f"moving {ref} to trash folder")

def main():
    # # pull sourceID and gamera ref
    with open(sys.argv[1], 'r') as csvfile:
        linereader = csv.reader(csvfile)
        access_token = login()
        for line in linereader:
            if line[0].startswith('pitt'): 
                sourceID = (line[0]).rsplit( ':' , maxsplit=1)[-1]
                gameraRef = line[1]
                # print(f"sourceID: {sourceID} and the corresponding ref: {gameraRef}")
                run_query(sourceID, gameraRef, access_token)
    
    # move refs in trashfile
    move_to_trash("move-to-trash.csv" , )


if __name__ == "__main__":
  main()


# #open file and begin
# with open(collection_refs, 'r') as file:
#     for line in file:
#         ref = line.strip()
#         move_url = f"https://pitt.preservica.com/api/entity/information-objects/{ref}/parent-ref"
#         response = requests.put(move_url, headers=headers, data=parent_ref)
#         if response.status_code in {403,404,422} or response.status_code != 202: 
#             err_msg = f"{ref} trouble moving with status code {response.status_code}"
#             logging.error(err_msg)
#         else: print(f"successfully started {ref} move to {parent_ref}")


# -------------------------------------------------------------------------------------------------------------------------- #

# response = requests.put(move_info_url, headers=headers, data='a18e4ca8-0ea9-4923-a8cc-92f00f437fcd')
# if response.status_code == 202: print(f"information object parent: {response.text}")
# else: print(f"error getting information object to another parent: {response.status_code}")

# response = requests.get(move_struct_url, headers=headers)
# if response.status_code == 200: print(f"structural object parents: {response.text}")
# else: print(f"error moving structural object parent: {response.status_code}")



# while True:
#     endpoint_url = f"https://pitt.preservica.com/api/entity/structural-objects/{SO_id}/children?ref={SO_id}&start={count}&max={max_items}"
#     print("endpoint url: " + endpoint_url)

#     headers = {
#     "Authorization": f"Bearer {access_token}",
#     }

#     response = requests.get(endpoint_url, headers=headers)

#     if response.status_code == 200:
#         print("Response Content-Type:", response.headers.get('Content-Type'))
#         try:
#             root = ET.fromstring(response.text)

#             ns = { 'default': 'http://preservica.com/EntityAPI/v7.4'}

#             print("parsed xml response: ")
            
#             for children in root.findall('default:Children', ns):
#                 with open('child_ref.csv', 'a', newline='') as file:
#                     for Child in children.findall('default:Child', ns):
#                         child_ref = Child.get('ref')
#                         child_title = Child.get('title')
#                         print(f"title: {child_title}")
#                         writer = csv.writer(file)
#                         writer.writerow([child_title, child_ref])
                        
#             print(f"count: {count}")
#             next_url = root.find('default:Paging//default:Next', ns)
#             if next_url is None:
#                 print("all data fetched")
#                 break
#             else:
#                 count += max_items
#                 print(f"fetching from {count} now")
#         except ET.ParseError as e:
#             print("error parsing xml - raw response: " + response.text)
#             break
#     else:
#         print(f"Error: {response.status_code}, {response.text}")
#         break


#pull the duplicated source ID - how many options come up in preservica

#check the refs to the refs in gamera
#if the ref doesn't match log that object to be deleted.

#once iterated through all the items to be deleted, began the move to the trash folder
