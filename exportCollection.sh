#!/bin/bash

# Set the PATH variable
export PATH=/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/sbin:/bin

#script to start collection export 
#./exportCollection.sh

#getting worker number
WORKER="${HOSTNAME##*-}"
WORKER="${WORKER%%.*}"
WORKER="${WORKER#0}" 

CSV_FILE='/mounts/transient/automation/reformatted.csv'
LOG_DIR='/mounts/transient/automation/logs'
ERROR_DIR='/mounts/transient/automation/err/'
LOCK_FILE="/mounts/transient/automation/lock/"$WORKER"export.lock"

CSV_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/csvUpdate.py'
PRESERVICA_EXPORT_SCRIPT='/mounts/transient/automation/islandoraPreservicaExport/preservica-mark-exported.sh'

ATTEMPTS=0
MAX_RETRIES=4

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
    DATE=$(date +"%A, %B %d, %Y %I:%M %p")
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
    DATE=$(date +"%A, %B %d, %Y %I:%M %p")
    echo "$DATE at $HOSTNAME - $MESSAGE" >> $LOG_FILE

}

# $1 is collection
# $2 is worker
bagit_creation(){
    COLLECTION=$1
    WORKER=$2

    update_log "$COLLECTION" "$WORKER" "drush starting"
    python3 "$CSV_SCRIPT" "$COLLECTION" 'status' 'bagit'
    output=$(drush --uri=https://gamera.library.pitt.edu/ --root=/var/www/html/drupal7/ --user=$USER create-islandora-bag --resume collection pitt:collection."$COLLECTION" 2>&1)

    if [ $? -ne 0 ]; then
        python3 "$CSV_SCRIPT" "$COLLECTION" 'status' 'ERROR'
        log_error "error running bagit drush command: $output"  
        return 1
    fi 
    update_log "$COLLECTION" "$WORKER" "drush completed"
}

# $1 is collection
# $2 is worker
DC_creation(){
    COLLECTION=$1
    WORKER=$2

    update_log "$COLLECTION" "$WORKER" "DC starting"
    python3 "$CSV_SCRIPT" "$COLLECTION" 'status' 'DC'
    output=$(wget -O /bagit/bags/'DC.xml' https://gamera.library.pitt.edu/islandora/object/pitt:collection.$COLLECTION/datastream/DC/view 2>&1)
    
    if [ $? -ne 0 ]; then
        python3 "$CSV_SCRIPT" "$COLLECTION" 'status' 'ERROR'
        log_error "error running DC command: $output"
        return 1
    fi 
    update_log "$COLLECTION" "$WORKER" "DC collected"
}


# $1 is collection
# $2 is worker
export_script(){
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "export script starting"
    python3 "$CSV_SCRIPT" "$COLLECTION" "status" "exportScript"
    output="$($PRESERVICA_EXPORT_SCRIPT 2>&1)"
    if [ $? -ne 0 ]; then
        python3 "$CSV_SCRIPT" $COLLECTION "status" "ERROR"
        log_error "mark exported script errored out with: $output"
        return 1
    fi 

    update_log "$COLLECTION" "$WORKER" "completed export script"
    #update status to Ready
    python3 "$CSV_SCRIPT" $COLLECTION "status" "Ready"
}

#restart worker by removing all files and changing status back to nan
refresh_worker() {
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "attempting refresh of collection"
    output=$(rm -rf /bagit/bags/* 2>&1)

    if [ $? -ne 0 ]; then
        log_error "error trying to remove content of bags/ directory: $output"
        return 1
    fi 
    update_log "$COLLECTION" "$WORKER" "collection refreshed"
    python3 "$CSV_SCRIPT" $COLLECTION "status" "nan"
}

#export collection
#1st parameter is worker
export_collection() {
    WORKER=$1
    echo "at $PWD"

    #check if worker is already assigned
    CHECK_COLLECTION=$(python3 "$CSV_SCRIPT" 'workerFind' $WORKER)
    
    if [ "$CHECK_COLLECTION" = "None" ]; then
        log_error "worker hasn't been assigned to a collection yet.. run archive03"
        exit 0
    elif [[ "$CHECK_COLLECTION" =~ ^[0-9]+$ ]]; then
        echo "worker $WORKER is currently in collection $CHECK_COLLECTION"
        COLLECTION=$CHECK_COLLECTION
        #check what stage it is at 
        TRANSFER_STATUS=$(python3 "$CSV_SCRIPT" 'workerStatus' $WORKER)
    else
        log_error_exit "error finding collection number for worker $WORKER"
    fi

    case $TRANSFER_STATUS in

        ERROR)
            echo "refreshing worker to start"
            refresh_worker "$COLLECTION" "$WORKER" || return $?
            ;&
        bagit | nan)
            echo "in bagit creation stage"
            bagit_creation "$COLLECTION" "$WORKER" || return $?
            ;&
        DC)
            echo "restarting DC stage"
            DC_creation "$COLLECTION" "$WORKER" || return $?
            ;&
        exportScript)
            echo "calling export script"
            export_script "$COLLECTION" "$WORKER" || return $?
            ;;
        Ready)
            update_log "$COLLECTION" "$WORKER" "collection is ready for archive"
            echo "collection is ready for archive"
            exit 0
            ;;
        *)
            log_error "unknown status found for worker $WORKER in collection $COLLECTION"
            return 1
            ;;
    esac

}

#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#main script
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#retry logic here
until [ "$ATTEMPTS" -eq "$MAX_RETRIES" ];
do 
    
    export_collection "$WORKER"
    return_code=$?
    if [ "$return_code" -ne 0 ]; then
        ATTEMPTS=$(($ATTEMPTS + 1))
    else
        echo "export successful!"
        break
    fi

done

#checking to see if it ran out of tries
if [ $ATTEMPTS -eq $MAX_RETRIES ]; then
    log_error_exit "max retries reached, check error log for more information"
fi 