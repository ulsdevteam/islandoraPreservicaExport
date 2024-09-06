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
    #print("Searching for worker number: " + worker_number)
    filter = df['worker'] == int(worker_number)
    index = df[filter].first_valid_index()
    if index is not None:
        #print("worker " + worker_number + " assigned to collection " + index)
        return index
    else:
        #print("worker not found")
        return "NULL"

# Check if the correct number of arguments is provided
if len(sys.argv) != 4:
    # Check if the first argument is "display"
    if len(sys.argv) == 1:
        print("Expected: python update_csv.py collection_number column_name value")
        exit(1)
    if sys.argv[1] == "display":
        #print_all_changes()
        exit(0)
    if sys.argv[1] == "workerFind" and sys.argv[2].isdigit():
        #print("finding worker " + sys.argv[2] + " and it's collection")
        worker_number=sys.argv[2]
        result = find_collection_number(worker_number)
        print(result)
        exit(0)
    else:     
        print("Expected: python update_csv.py collection_number column_name value OR display OR assign worker_number")
        exit(1)
else:
    # Read parameters from command line
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


# Track the change with date
today = date.today().strftime("%m/%d/%Y")
if today not in changes:
    changes[today] = []
changes[today].append({
    "time": datetime.now().strftime("%H:%M:%S"),
    "collection_number": collection_number,
    "column": col,
    "value": function
})

#write back to the csv and save the changes made to the json
df.to_csv(CSV_FILE, index=False)
save_changes(changes)


#function to print changes by specific date?

#function to find where a worker is / which worker is available?

#function to erase all data in json?