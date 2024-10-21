#!/bin/bash

# Set the PATH variable
export PATH=/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/sbin:/bin

#script to start collection ingest

#getting worker number
WORKER="${HOSTNAME##*-}"
WORKER="${WORKER%%.*}"
WORKER="${WORKER#0}" 

CSV_FILE='/mounts/transient/automation/reformatted.csv'
LOG_DIR='/mounts/transient/automation/logs'
ERROR_DIR='/mounts/transient/automation/err/'
LOCK_FILE="/mounts/transient/automation/lock/"$WORKER"ingest.lock"

CSV_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/csvUpdate.py'
PRESERVICA_INGEST_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/preservica-mark-ingested.sh'
OPEX_DIR="/mounts/transient/automation/islandoraPreservicaExport/opex-logs/"$WORKER""

#create a lock file for cron jobs

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
    DATE=$(date +"%I:%M:%S %p")
    echo "$DATE: $1" >> $ERROR_FILE
}

log_error_exit() {
    update_err "$1"
    exit 1
}

log_error() {
    update_err "$1"
    echo "error.log updated with: $1"
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
    DATE=$(date +"%I:%M:%S %p")
    echo "$DATE at $HOSTNAME - $MESSAGE" >> $LOG_FILE

}

#ingest script to run through all collection.csv files

#LOCAL_OPEX_DIR="/home/emv38/islandoraPreservicaExport/opex-logs/"$WORKER""
for FILE in "$OPEX_DIR"/collection.*.csv; do
    #for FILE in "$LOCAL_OPEX_DIR"/collection.*.csv; do
    if [ -f "$FILE" ]; then

        COLLECTION=$(basename "$FILE" .csv) 
        COLLECTION="${COLLECTION#collection.}"
        echo "collection number: $COLLECTION"
        update_log "$COLLECTION" "$WORKER" "attempting ingest script for $FILE"
        
        if $PRESERVICA_INGEST_SCRIPT "$FILE"; then
            update_log "$COLLECTION" "$WORKER" "ingest script completed - removing $FILE now"

            #updating with current date to show ingest has completed
            current_date=$(date +"%m/%d/%Y")
            python3 "$CSV_SCRIPT" "$COLLECTION" 'exportDate' "$current_date"

            if ! rm "$FILE"; then
                log_error "Error removing $FILE"
            fi
        else 
            log_error "Error running ingest script for $FILE"
        fi
    fi 
done