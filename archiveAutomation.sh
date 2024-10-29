#!/bin/bash

# Set the PATH variable
export PATH=/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/sbin:/bin

ERROR_DIR='/mounts/transient/automation/err/'

LOG_DIR='/mounts/transient/automation/logs'
LOCK_FILE="/mounts/transient/automation/lock/archive03.lock"

PITT_PAX_V2_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/bagit-pax/pitt_pax_v2.py'
CSV_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/csvUpdate.py'
XML_ACCESS_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/xmlaccess.py'

TEMP_FILE='/mounts/transient/automation/temp.log'

#lockfile generation
if [ -f "$LOCK_FILE" ]; then
    #read PID
    LOCKED_PID=$(cat "$LOCK_FILE")
    #is process still running?
    if ps -p "$LOCKED_PID"; then
        log_error "script currently running with PID: $LOCKED_PID, exiting"
        exit 0
    else
        log_error "old lock file, removing"
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


#what kind of error - in case you need to restart a collection
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
    DATE=$(date +"%A, %B %d, %Y %I:%M %p")
    echo "$DATE at $HOSTNAME: $1" >> $ERROR_FILE
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
    DATE=$(date +"%A, %B %d, %Y %I:%M %p")
    echo "$DATE at $HOSTNAME - $MESSAGE" >> $LOG_FILE

}

#determine if gmworker has a collection ready for upload
#send in the number as the parameter
#return 0 is ready, return 1 if transfer still in progress, and 2 if needs new collection
check_worker_status() {
 
    worker_directory="/mounts/transient/pa-gmworker-0$1/bags/"
    STATUS=$(python3 $CSV_SCRIPT "workerStatus" "$1")
    #echo "status: $STATUS"
    if [ "$STATUS" = "Ready" ] || [ "$STATUS" = "archiveERROR" ]; then
        if [ "$(ls $worker_directory | grep DC.xml)" ]; then
            return 0;
        else
            log_error_exit "issue finding DC.xml within $worker_directory"
        fi
    elif [ "$STATUS" = "NEEDNEWCOLLECTION" ]; then
        echo "status of worker $1 is None meaning it's ready for a new collection"
        return 3;
    elif [ "$STATUS" = "ERROR" ]; then
        log_error "ERROR found in worker $1 server"
        return 4;
    elif [ "$STATUS" = "removing" ]; then
        echo "removing collections"
        return 2;
    else
        log_error "other error found within worker $1 with status: $STATUS"
        return 4;
    fi 

}

#pull collection number from DC.xml file
#param 1 is worker number
get_collection_number() {
    
    collection_directory="/mounts/transient/pa-gmworker-0$1/bags/"

    #get collection number through python3 script
    DC_FILE=$(ls $collection_directory | grep DC.xml)
    
    collection_number=$(python3 $XML_ACCESS_SCRIPT "$collection_directory/$DC_FILE")
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
    ERROR_OUTPUT=$(rm -rf /mounts/transient/pittpax/Source/*)
    if [ $? -ne 0 ]; then
        log_error_exit "Error removing /mounts/transient/pittpax/Source/* at $WORKER_NAME with collection $2: $ERROR_OUPUT"
    fi

    update_log "$2" "$1" "making new directory in Source"
    mkdir /mounts/transient/pittpax/Source/collection."$2"/
    if [ $? -ne 0 ]; then
        log_error_exit "Error making directory /mounts/transient/pittpax/Source/collection.$2/"
    fi

    update_log "$2" "$1" "copying DC.xml to Source directory"
    cp /mounts/transient/$WORKER_NAME/bags/DC.xml /mounts/transient/pittpax/Source/collection.$2/
    if [ $? -ne 0 ]; then
        log_error_exit "Error copying /mounts/transient/$WORKER_NAME/bags/DC.xml to /mounts/transient/pittpax/Source/collection.$2/"
    fi 

    # Count total zip files
    total_files=$(ls /mounts/transient/$WORKER_NAME/bags/*.zip | wc -l)
    processed_files=0
    if [ "$total_files" -eq 0 ]; then
        log_error_exit "No zip files found in /mounts/transient/$WORKER_NAME/bags/"
    fi

    update_log "$2" "$1" "unzipping items into Source directory"
    for j in /mounts/transient/$WORKER_NAME/bags/*.zip; do 
        #update_log "$2" "$1" "$j"
        echo "$j"
        unzip "$j" -d /mounts/transient/pittpax/Source/collection.$2/
        if [ $? -ne 0 ]; then
            log_error_exit "Error unzipping file $j to /mounts/transient/pittpax/Source/collection.$2/"
        fi
        processed_files=$((processed_files + 1))
        PERCENT=$((processed_files * 100 / total_files))
        update_log "$2" "$1" ""$PERCENT"% completed.."
    done
    
}

run_automated_pittPax() {
    COLLECTION=$1

    python3 $CSV_SCRIPT "$COLLECTION" "status" "ppax"
    output=$(python3 "$PITT_PAX_V2_SCRIPT" "1" "ALL" "1" 2>&1)
    #python3 "$PITT_PAX_V2_SCRIPT" "1" "ALL" "1"
    if [ $? -ne 0 ]; then
        log_error "unable to run the automated pitt pax script, see output: $output"
    fi  

}

#remove all previous collections from shared mount of gmworkers, and pittpax location - 
# $1 parameter is the gmworker server to delete from
remove_old_collections() {
    

    output=$(rm -rf /mounts/transient/pittpax/Master/Final/* 2>&1)
    if [ $? -ne 0 ]; then
        log_error "$output"
    fi

    #echo "removing from: /mounts/transient/$1/bags/*"

    output=$(rm -rf /mounts/transient/$1/bags/* 2>&1)
    if [ $? -ne 0 ]; then
        log_error "$output"
    fi

}

#assign worker to new collection
assign_worker() {
    WORKER=$1
    python3 $CSV_SCRIPT workerAssign "$WORKER" || log_error_exit "error in assigning new collection to worker $WORKER"
}

#update temp dir
#collection is 1 
#worker is 2
#adding last line
add_to_temp() {
    COLLECTION=$1
    WORKER=$2

    CHECK_LOG_FILE="$LOG_DIR/$COLLECTION-$WORKER.log"
    
    if [[ ! -f "$CHECK_LOG_FILE" ]]; then
        log_error_exit "error finding log file $COLLECTION-$WORKER.log"
    fi 

    if [[ ! -f "$TEMP_FILE" ]]; then
        touch "$TEMP_FILE"
    fi
    #date variable
    DATE=$(date +"%b %d, %Y")
    echo ""$DATE" | "$COLLECTION" | "$WORKER"" >> "$TEMP_FILE"
    #tail -1 "$CHECK_LOG_FILE" >> "$TEMP_FILE"
    if [ $? -ne 0 ]; then
        log_error_exit "Error adding the last line of $COLLECTION-$WORKER.log to $TEMP_FILE"
    fi

}

#-----------------------------------------------------------------------------------------
#main script starts
#-----------------------------------------------------------------------------------------
# CONTINUE=true
for ((i=1 ; i<=4 ; i++ ));
do

    check_worker_status "$i"
    worker_status=$?
    COLLECTION=$(get_collection_number "$i")

    # 0 - Ready to start from the beginning
    # 1 - automated pittpax script
    # 2 - removing old collections
    # 3 - assigning new collections
    # * - unkown error code
    
    case $worker_status in 
    0)
        COLLECTION=$(get_collection_number $i)
        if [ -z "$COLLECTION" ] || [ "$COLLECTION" -eq 1 ]; then
            python3 $CSV_SCRIPT "$COLLECTION" "status" "archiveERROR"
            log_error_exit "Error getting a valid collection number for pa-gmworker-0$i"
        fi

        echo "starting transfer now"
        update_log "$COLLECTION" "$i" "archive03 transfer starting"

        python3 $CSV_SCRIPT "$COLLECTION" "status" "transferring"
        start_transfer "$i" "$COLLECTION"

        python3 $CSV_SCRIPT "$COLLECTION" "status" "transfered"
        if [ $? -ne 0 ]; then
            python3 $CSV_SCRIPT "$COLLECTION" "status" "archiveERROR"
            log_error_exit "Error csvUpdate.py didn't update status successfully for collection $COLLECTION in pa-gmworker-0$i"
        fi      
        
        # #separate method for python script to run
        # update_log "$COLLECTION" "$i" "starting pitt pax script"
        # run_automated_pittPax
        # if [ $? -ne 0 ]; then 
        #     log_error_exit "error running automated pittpax script for collection $COLLECTION in pa-gmworker-0$i"
        # fi
        # update_log "$COLLECTION" "$i" "pitt pax script completed"


        # update_log "$COLLECTION" "$i" "removing collections"
        # remove_old_collections "pa-gmworker-0$i"
        # if [ $? -ne 0 ]; then 
        #     log_error_exit "error removing collections for collection $COLLECTION in pa-gmworker-0$i"
        # fi
        

        # update_log "$COLLECTION" "$i" "$COLLECTION exported from pa-gmworker-0$i updating csv..."
        # python3 $CSV_SCRIPT "$COLLECTION" "status" "Complete"
        # if [ $? -ne 0 ]; then
        #     log_error_exit "Error csvUpdate.py didn't update status to Complete successfully for collection $COLLECTION in pa-gmworker-0$i"
        # fi   

        # #assign a new collection
        # assign_worker "$i"
        # if [ $? -ne 0 ]; then 
        #     log_error_exit "error assigning new collection for pa-gmworker-0$i"
        # fi

        # #add to a temp log
        # add_to_temp "$COLLECTION" "$i"
        # if [ $? -ne 0 ]; then 
        #     log_error_exit "error adding to temp log for pa-gmworker-0$i"
        # fi

        ;&
    1) 
        echo "automated pittpax starting"

        #separate method for python script to run
        update_log "$COLLECTION" "$i" "starting pitt pax script"
        run_automated_pittPax "$COLLECTION"
        if [ $? -ne 0 ]; then 
            python3 $CSV_SCRIPT "$COLLECTION" "status" "archiveERROR"
            log_error_exit "error running automated pittpax script for collection $COLLECTION in pa-gmworker-0$i"
        fi
        update_log "$COLLECTION" "$i" "pitt pax script completed"

        ;&
    2)
        echo "removing old collections"

        update_log "$COLLECTION" "$i" "removing collections"
        python3 $CSV_SCRIPT "$COLLECTION" "status" "removing"
        remove_old_collections "pa-gmworker-0$i"
        if [ $? -ne 0 ]; then
            log_error_exit "error removing collections for collection $COLLECTION in pa-gmworker-0$i"
        fi

        update_log "$COLLECTION" "$i" "$COLLECTION exported from pa-gmworker-0$i updating csv..."
        python3 $CSV_SCRIPT "$COLLECTION" "status" "Complete"
        if [ $? -ne 0 ]; then
            log_error_exit "Error csvUpdate.py didn't update status to Complete successfully for collection $COLLECTION in pa-gmworker-0$i"
        fi  
        
        ;&
    3)
        echo "assign new collection to worker"
        assign_worker "$i"
        if [ $? -ne 0 ]; then 
            log_error_exit "error assigning new collection for pa-gmworker-0$i"
        fi

        ;;
    *)
        log_error_exit "unknown status code for worker $i: $worker_status"
        ;;
    esac

done

# if [ -f "$TEMP_FILE" ]; then
#     #has items in it that need to be mailed
#     DATE=$(date)
#     #echo "$HOSTNAME run completed at $DATE" | mutt -a "$TEMP_FILE" -s 'Archive transfers complete - wait for OPEX' emv38@pitt.edu

#     # rm -f "$TEMP_FILE"
#     # if [ $? -ne 0 ]; then 
#     #     log_error_exit "Error removing $TEMP_FILE - must manually do so before next cron"
#     # fi

# fi 

#-----------------------------------------------------------------------------------------