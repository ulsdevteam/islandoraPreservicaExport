#!/bin/bash

ERROR_DIR='/mounts/transient/automation/err/'
#ERRORLOG=~/"automationScripts/error.log"
LOG_DIR='/mounts/transient/automation/logs/'
LOCK_FILE="/mounts/transient/automation/lock/archive03.lock"


#lockfile generation
if [ -f "$LOCK_FILE" ]; then
    #read PID
    LOCKED_PID=$(cat "$LOCK_FILE")
    #is process still running?
    if ps -p "$LOCKED_PID"; then
        echo "script currently running with PID: $LOCKED_PID, exiting"
        exit 0
    else
        echo "old lock file, removing"
        rm -f "$LOCK_FILE"
    fi 
fi

#create lock file with current PID
echo "$$" > $LOCK_FILE

#unlock on exit
unlock() {
    rm -f "$LOCK_FILE"
}
trap unlock EXIT

log_error_exit() {
    update_err "$1"
    exit 1
}

log_error() {
    update_err "$1"
    echo "error.log updated with: $1"
}

# $1 is the message
update_err() {

    if [ -z "$ERROR_DIR" ]; then
        echo "err directory not set"
        exit 1
    fi

    if [ ! -d "$ERROR_DIR" ]; then
        echo "directory not found"
        exit 1
    fi 

    #contruct err file
    CURR_DAY=$(date +"%m-%d-%Y")
    ERROR_FILE="$ERROR_DIR/$CURR_DAY-$HOSTNAME-err.log"

    #does the log file already exist?
    if [ ! -f "$ERROR_FILE" ]; then
        echo "log file not found, creating new log"
        touch "$ERROR_FILE"
    else
        echo "$ERROR_FILE exists, updating.."
    fi
    DATE=$(date)
    echo "$DATE: $1" >> $ERROR_FILE
}

#log file update
# $1 is collection
# $2 is worker
# $3 is the message written to file
update_log() {
    COLLECTION=$1
    WORKER=$2
    MESSAGE=$3

    #is log dir set?
    if [ -z "$LOG_DIR" ]; then
        log_error_exit "Log directory not set"
    fi 

    #is there a log dir inside the shared folder?
    if [ ! -d "$LOG_DIR" ]; then
        log_error_exit "log directory not found"
    fi 

    #contruct log file
    LOG_FILE="$LOG_DIR/$COLLECTION-$WORKER.log"

    #does the log file already exist?
    if [ ! -f "$LOG_FILE" ]; then
        echo "log file not found, creating new log"
        touch "$LOG_FILE"
    else
        echo "$LOG_FILE exists, updating.."
    fi 

    #date variable
    DATE=$(date)
    echo "$DATE - $MESSAGE" >> $LOG_FILE

}

#determine if gmworker has a collection ready for upload
#send in the number as the parameter
#return 0 is ready, return 1 if transfer still in progress, and 2 if needs new collection
check_worker_status() {
 
    worker_directory="/mounts/transient/pa-gmworker-0$1/bags/"
    STATUS=$(python csvUpdate.py "workerStatus" "$1")

    if [ "$STATUS" = "Ready" ]; then
        if [ "$(ls $worker_directory | grep DC.xml)" ]; then
            return 0;
        else
            log_error_exit "issue finding DC.xml within $worker_directory"
        fi
    elif [ "$STATUS" = "None" ]; then
        echo "status of worker $1 is None meaning it's ready for a new collection"
        return 2;
    else
        #echo "gmworker-0$1 still transferring.."
        return 1;
    fi 

}

#pull collection number from DC.xml file
#param 1 is worker number
get_collection_number() {
    
    collection_directory="/mounts/transient/pa-gmworker-0$1/bags/"

    #get collection number through python script
    DC_FILE=$(ls $collection_directory | grep DC.xml)
    
    collection_number=$(python xmlaccess.py "$collection_directory/$DC_FILE")
    exit_code=$?

    if [ $exit_code -eq 1 ]; then
    log_error_exit "xmlaccess.py script encountered an error for pa-gmworker-0$1. Exit code: $exit_code"
    elif [ $exit_code -eq 0 ]; then
        echo $collection_number
    else
        log_error_exit "xmlaccess.py script returned an unexpected exit code for pa-gmworker-0$1: $exit_code"
    fi

}

#1 is worker
#2 is collection
start_transfer() {

    echo "transfering collection $2 from pa-gmworker-0$1"
    WORKER_NAME=pa-gmworker-0"$1"

    update_log "$2" "$1" "removing items from Source directory"
    rm -fR /mounts/transient/pittpax/Source/*
    if [ $? -ne 0 ]; then
        log_error_exit "Error removing /mounts/transient/pittpax/Source/* at $WORKER_NAME with collection $2"
    fi

    update_log "$2" "$1" "making new directory in Source"
    mkdir /mounts/transient/pittpax/Source/collection."$2"/
    if [ $? -ne 0 ]; then
        log_error_exit "Error making directory /mounts/transient/pittpax/Source/collection.$2/"
    fi

    update_log "$2" "$1" "copying items to Source directory"
    cp /mounts/transient/$WORKER_NAME/bags/DC.xml /mounts/transient/pittpax/Source/collection.$2/
    if [ $? -ne 0 ]; then
        log_error_exit "Error copying /mounts/transient/$WORKER_NAME/bags/DC.xml to /mounts/transient/pittpax/Source/collection.$2/"
    fi 

    update_log "$2" "$1" "unzipping items into Source directory"
    for j in /mounts/transient/$WORKER_NAME/bags/*.zip; do 
        update_log "$2" "$1" "$j"
        #echo "$j"
        unzip "$j" /mounts/transient/pittpax/Source/collection.$2/
        if [ $? -ne 0 ]; then
            log_error_exit "Error unzipping file $j to /mounts/transient/pittpax/Source/collection.$2/"
        fi
    done
    
}

run_automated_pittPax() {
    
    pitt_pax_v2_path=/home/$USER/islandoraPreservicaExport/bagit-pax/pitt_pax_v2.py
   
    python "$pitt_pax_v2_path" "1" "ALL" "1" || log_error_exit "unable to run the automated pitt pax script - proceeding with interactive"
    #python "$pitt_pax_v2_path" "first_step" "c_f_input" "send_to_s3"
}

#remove all previous collections from shared mount of gmworkers, and pittpax location - 
# $1 parameter is the gmworker server to delete from
remove_old_collections() {
    
    #rm -fR /mounts/transient/pittpax/Master/Final/* 2>> $ERRORLOG

    ERROR_MSG=$(rm -rf /mounts/transient/pittpax/Master/Final/* 2>&1)

    if [ $? -ne 0 ]; then
        log_error_exit "$ERROR_MSG"
    fi

    
    #echo "removing from: /mounts/transient/$1/bags/*"

    ERROR_MSG=$(rm -fR /mounts/transient/$1/bags/* 2>&1)

    #rm -fR /mounts/transient/$1/bags/* 2>> $ERRORLOG
    if [ $? -ne 0 ]; then
        log_error_exit "$ERROR_MSG"
    fi

}

#assign worker to new collection
assign_worker() {
    WORKER=$1
    python csvUpdate.py workerAssign "$WORKER" || log_error_exit "error in assigning new collection to worker $WORKER"
}

#-----------------------------------------------------------------------------------------
#main script starts
#-----------------------------------------------------------------------------------------
CONTINUE=true
for ((i=1 ; i<=4 ; i++ ));
do

    if [ "$CONTINUE" = false ]; then
        log_error_exit "FORCE EXIT: exiting program at loop index $i"
    fi

    check_worker_status "$i"
    worker_status=$?
    
    case $worker_status in 
    0)
        COLLECTION=$(get_collection_number $i)
        if [ -z "$COLLECTION" ] || [ "$COLLECTION" -eq 1 ]; then
            log_error_exit "Error getting a valid collection number for pa-gmworker-0$i"
        fi
        echo "starting transfer now"
        # update_log "$COLLECTION" "$i" "archive03 transfer starting"

        # start_transfer "$i" $COLLECTION

        # # python csvUpdate.py "$COLLECTION" "worker" $i
        # # if [ $? -ne 0 ]; then
        # #     log_error_exit "Error csvUpdate.py update worker successfully for collection $COLLECTION in pa-gmworker-0$i"
        # # fi
        # python csvUpdate.py "$COLLECTION" "status" "In Progress"
        # if [ $? -ne 0 ]; then
        #     log_error_exit "Error csvUpdate.py didn't update status successfully for collection $COLLECTION in pa-gmworker-0$i"
        # fi      
        
        # #separate method for python script to run
        # update_log "$COLLECTION" "$i" "starting pitt pax script"
        # run_automated_pittPax
        # if [ $? -ne 0 ]; then 
        #     log_error_exit "error running automated pittpax script for collection $COLLECTION in pa-gmworker-0$i"
        # fi
        # update_log "$COLLECTION" "$i" "pitt pax script completed"


        # update_log "$COLLECTION" "$i" "removing collections"
        # remove_old_collections "pa-gmworker-0$i"
        

        # update_log "$COLLECTION" "$i" "$COLLECTION exported from pa-gmworker-0$i updating csv..."
        # python csvUpdate.py "$COLLECTION" "status" "Complete"
        # if [ $? -ne 0 ]; then
        #     log_error_exit "Error csvUpdate.py didn't update status to Complete successfully for collection $COLLECTION in pa-gmworker-0$i"
        # fi   

        # #assign a new collection
        # assign_worker "$i"
        ;;
    1) 
        echo "pa-gmworker-0$i still running transfer"
        ;;
    2)
        echo "pa-gmworker-0$i ready for new collection"
        assign_worker "$i"
        ;;
    *)
        log_error_exit "unknown status code for worker $i"
        ;;
    esac

    read -p "continue? (Y or N): " USER_INPUT
    if [ "$USER_INPUT" = "N" ]; then
        CONTINUE=false
    fi

done

#display all the changes made after all four have been run
read -p "looped through all servers, restart (Y) or exit(N): " INPUT
if [ "$INPUT" = "Y" ]; then
    bash archiveAutomation.sh
elif [ "$INPUT" = "N" ]; then
    exit 0
else
    log_error_exit "ERROR at loop end didn't type either Y/N, instead typed $INPUT"
fi

#-----------------------------------------------------------------------------------------