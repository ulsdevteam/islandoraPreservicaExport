#import numpy as np
from curses.ascii import isdigit
import pandas as pd 
from datetime import date, datetime
import sys
import csv
import json 
import os

#----------------------------------------------------------------------------------------#
#csv is set up such that:
#----------------------------------------------------------------------------------------#
# Collection Name,       Collection ID,            Include,    Done,         In Progress
#    (int)            (pitt:collection.###)         (1/0)    MM/DD/YYYY       (1-4)
#----------------------------------------------------------------------------------------#
# Initialize the dictionary to store changes
#json?
CHANGES_FILE='/mounts/transient/automation/changes.json'
CSV_FILE='/mounts/transient/automation/reformatted.csv'
ERROR_LOG='/home/emv38/automationScripts/error.log'

# Initialize the dictionary to store changes
def load_changes():
    if os.path.exists(CHANGES_FILE):
        with open(CHANGES_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_changes(changes):
    with open(CHANGES_FILE, 'w') as file:
        json.dump(changes, file, indent=4)

changes = load_changes()

#try to read the csv file
try:
    df = pd.read_csv(CSV_FILE)
    df.head()
except FileNotFoundError:
    print("Error: 'reformatted.csv' file not found.")
    exit(1)

#set the index to the collection number but keep the column intact still
df.set_index("collection number", drop=False, inplace=True)

# Function to print all tracked changes
# def print_all_changes():
#     today = date.today().strftime("%m/%d/%Y")
#     print("All changes made to the CSV as of {}:".format(today))
#     for change_date, changes_list in changes.items():
#         print(f"\nDate: {change_date}")
#         for change in changes_list:
#             print(f"Row with collection number {change['collection_number']}, Column '{change['column']}' updated to '{change['value']}' at '{change['time']}'")

#find collection number that worker is at 
def find_collection_number(worker_number):
    filter = df['worker'] == int(worker_number)
    index = df[filter].first_valid_index()
    if index is not None:
        return index
    else:
        return None
    
#assign collection number to a worker
def assign_new_collection(worker_number):
    if (find_collection_number(worker_number)) is None:
        available_collections = df[(df['Include'] == 1) & ((df['status'] != 'Complete') & (df['status'] != 'LARGE') )]
        if available_collections.empty:
            return None
        new_collection = available_collections.index[0]
        df.loc[new_collection, 'worker'] = int(worker_number)
        return new_collection
    return None

def update_csv():
    #write back to the csv and save the changes made to the json
    df.to_csv(CSV_FILE, index=False)
    save_changes(changes)

def track_change(collection, column, value):
    # Track the change with date
    today = date.today().strftime("%m/%d/%Y")
    if today not in changes:
        changes[today] = []
    changes[today].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "collection_number": collection,
        "column": column,
        "value": value
    })
    
# Check if the correct number of arguments is provided
if len(sys.argv) != 4:
    # Check if the first argument is "display"
    if len(sys.argv) == 1:
        print("Expected: python update_csv.py collection_number column_name value")
        exit(1)
    if sys.argv[1] == "display":
        exit(0)
    if sys.argv[1] == "workerFind" and sys.argv[2].isdigit():
        worker_number=sys.argv[2]
        result = find_collection_number(worker_number)
        print(result)
        exit(0)
    if sys.argv[1] == "workerAssign" and sys.argv[2].isdigit():
        result = assign_new_collection(sys.argv[2])
        track_change(result, 'worker', int(sys.argv[2]))
        update_csv()
        print(result)
        exit(0)
    else:     
        print("Expected: python update_csv.py collection_number column_name value OR display OR assign worker_number")
        exit(1)
else:
    collection_number = (sys.argv[1])
    col = sys.argv[2]
    function = sys.argv[3]

    if col not in df.columns:
        print("Error: column entered not found")
        exit(1)

    if collection_number not in df.index:
        print("Error: collection number entered not found")
        print("'{collection_number}' not found within '{df.index}'")
        exit(1)   

    #update the value if it's worker then it should be a float
    if col == "worker":
        df.loc[collection_number, col] = int(function)
    else:
        df.loc[collection_number, col] = function

    #if process is complete remove the gmworker and update the exportdate for today
    if function == "Complete":
        df.loc[collection_number, "worker"] = ""
        df.loc[collection_number, "exportDate"] = date.today().strftime("%m/%d/%Y")
    
    track_change(collection_number, col, function)
    update_csv()

