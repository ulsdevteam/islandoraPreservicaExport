#import numpy as np
from curses.ascii import isdigit
import pandas as pd 
from datetime import date, datetime
import sys
import json 
import os
#import portalocker
from filelock import FileLock, Timeout
# import fcntl
# import threading



#----------------------------------------------------------------------------------------#
#csv is set up such that:
#----------------------------------------------------------------------------------------#
# Collection Name,       Collection ID,            Include,    Done,         In Progress
#    (int)            (pitt:collection.###)         (1/0)    MM/DD/YYYY       (1-4)
#----------------------------------------------------------------------------------------#
# Initialize the dictionary to store changes
#json?
CHANGES_FILE = '/mounts/transient/automation/changes.json'
CSV_FILE = '/mounts/transient/automation/reformatted.csv'
ERROR_LOG = '/home/emv38/automationScripts/error.log'
LOCK_FILE = '/mounts/transient/automation/csvlockfile.lock'

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
        available_collections = df[(df['Include'].eq(1)) & 
            ((df['status'].ne('Complete')) & (df['status'].ne('LARGE')) ) &
            ((df["worker"].eq(0)))
        ]
        if available_collections.empty:
            return None
        new_collection = available_collections.index[0]
        df.loc[new_collection, 'worker'] = int(worker_number)
        update_value(new_collection, 'worker', worker_number)
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

def worker_status(worker):
    collection = find_collection_number(worker)
    if collection is None: return "NEEDNEWCOLLECTION"
    else:
        status = df.loc[collection, 'status']
    return status

# return 1 for updating csv
# return 2 for worker related commands
def check_arguments():
    if len(sys.argv) < 3:
        print("Not enough parameters")
        exit(1)
    # if not sys.argv[2].isdigit():
    #     print("The second argument must be a digit.")
    #     exit(1)
    return 1 if len(sys.argv) == 4 else 2


def validate_collection_columns(collection, column):
    if column not in df.columns:
        print("Error: column entered not found")
        exit(1)

    if collection not in df.index:
        print("Error: collection number entered not found")
        print("'{collection}' not found within '{df.index}'")
        exit(1) 

def update_value(collection, column, value):
    #update the value if it's worker then it should be a float
    lock = FileLock(LOCK_FILE)
    try:
        # Try to acquire the lock with a timeout
        with lock.acquire(timeout=10):  # Wait for up to 10 seconds for the lock
            # Writing to the CSV file
            if column == "worker":
                df.loc[collection, column] = int(value)
            else:
                df.loc[collection, column] = value

            #if process is complete remove the gmworker
            if value == "Complete":
                df.loc[collection, "worker"] = ""
                #df.loc[collection, "exportDate"] = date.today().strftime("%m/%d/%Y")
            track_change(collection, column, value)
            update_csv()
    except Timeout:
        print("Could not acquire lock, another process is writing to the file.")
    except Exception as e:
        print("Error occured during filelock attempt: " + e)


def main():

    # #maybe shared lock for reading?
    # with open(LOCK_FILE, 'w') as lock_file:
    #     portalocker.lock(lock_file, portalocker.LOCK_EX)

    #main script where all the helper functions start
    check = check_arguments()

    if check == 1:
        #updating the csv
        collection_number = (sys.argv[1])
        column = sys.argv[2]
        value = sys.argv[3]
        validate_collection_columns(collection_number, column)
        update_value(collection_number, column, value)

    if check == 2:
        #worker related commands
        command = sys.argv[1]
        worker = sys.argv[2]
        if command == "workerStatus":
            result = worker_status(worker)
        elif command == "workerFind":
            result = find_collection_number(worker)
        elif command == "workerAssign":
            result = assign_new_collection(worker)
        else:
            print("error reading command")
            exit(1)
        print(str(result))


#start main
if __name__ == "__main__":
    main()
