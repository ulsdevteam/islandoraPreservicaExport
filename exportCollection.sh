#!/bin/bash

#script to start collection export 
#./exportCollection.sh "{collection number}"

#getting worker number
WORKER="${HOSTNAME##*-}"
WORKER="${WORKER%%.*}"
WORKER="${WORKER#0}" 

CSV_FILE='/mounts/transient/automation/reformatted.csv'
LOG_DIR='/mounts/transient/automation/logs'
ERROR_DIR='/mounts/transient/automation/err/'
LOCK_FILE="/mounts/transient/automation/lock/"$WORKER"export.lock"

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
    DATE=$(date)
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
    DATE=$(date)
    echo "$DATE - $MESSAGE" >> $LOG_FILE

}

# $1 is collection
# $2 is worker
bagit_creation(){
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "drush starting"
    python3 csvUpdate.py "$COLLECTION" 'status' 'bagit'
    #sudo -u karimay drush --uri=https://gamera.library.pitt.edu/ --root=/var/www/html/drupal7/ --user=$USER create-islandora-bag --resume collection pitt:collection.$COLLECTION
    sudo su -c "drush --uri=https://gamera.library.pitt.edu/ --root=/var/www/html/drupal7/ --user=$USER create-islandora-bag --resume collection pitt:collection.$COLLECTION" -s /bin/bash karimay

    if [ $? -ne 0 ]; then
        python3 csvUpdate.py "$COLLECTION" 'status' 'ERROR'
        log_error_exit "error running bagit drush command"  
    fi 
    update_log "$COLLECTION" "$WORKER" "drush completed"
}

# $1 is collection
# $2 is worker
DC_creation(){
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "DC starting"
    python3 csvUpdate.py "$COLLECTION" 'status' 'DC'
    #sudo -u karimay wget -O /bagit/bags/'DC.xml' https://gamera.library.pitt.edu/islandora/object/pitt:collection.$COLLECTION/datastream/DC/view
    sudo su -c "wget -O /bagit/bags/'DC.xml' https://gamera.library.pitt.edu/islandora/object/pitt:collection.$COLLECTION/datastream/DC/view" -s /bin/bash karimay
    
    if [ $? -ne 0 ]; then
        python3 csvUpdate.py "$COLLECTION" 'status' 'ERROR'
        log_error_exit "error running DC command"
    fi 
    update_log "$COLLECTION" "$WORKER" "DC collected"
}


# $1 is collection
# $2 is worker
export_script(){
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "export script starting"
    python3 csvUpdate.py "$COLLECTION" "status" "exportScript"
    SCRIPT_OUTPUT="$(./preservica-mark-exported.sh 2>&1)"
    if [ $? -ne 0 ]; then
        python3 csvUpdate.py $COLLECTION "status" "ERROR"
        log_error_exit "mark exported script errored out: $SCRIPT_OUTPUT"
    fi 
    #./preservica-mark-exported.sh
    update_log "$COLLECTION" "$WORKER" "completed export script"
    #update status to Ready
    python3 csvUpdate.py $COLLECTION "status" "Ready"
}

#export collection
#1st parameter is collection number
#2nd parameter is worker number
export_collection() {
    WORKER=$1
    echo "at $PWD"

    #check if worker is already assigned
    CHECK_COLLECTION=$(python3 csvUpdate.py 'workerFind' $WORKER)
    
    if [ "$CHECK_COLLECTION" = "None" ]; then
        echo "worker hasn't been assigned to a collection yet.. run archive03"
        exit 1
    elif [[ "$CHECK_COLLECTION" =~ ^[0-9]+$ ]]; then
        echo "worker $WORKER is currently in collection $CHECK_COLLECTION"
        COLLECTION=$CHECK_COLLECTION
        #check what stage it is at 
        TRANSFER_STATUS=$(python3 csvUpdate.py 'workerStatus' $WORKER)
    else
        log_error_exit "error finding collection number for worker $WORKER"
    fi

    case $TRANSFER_STATUS in

        ERROR)
            echo "refreshing worker to start"
            refresh_worker "$COLLECTION" "$WORKER"
            ;&
        bagit | nan)
            echo "in bagit creation stage"
            bagit_creation "$COLLECTION" "$WORKER"
            ;&
        DC)
            echo "restarting DC stage"
            DC_creation "$COLLECTION" "$WORKER"
            ;&
        exportScript)
            echo "calling export script"
            export_script "$COLLECTION" "$WORKER"
            ;;
        Ready)
            echo "collection is ready for archive"
            exit 0
            ;;
        *)
            log_error_exit "unknown status found for worker $WORKER in collection $COLLECTION"
            ;;
    esac

}


mark_ingested(){
    COLLECTION=$1
    if [ "$PWD" = "/home/$USER/islandoraPreservicaExport" ]; then
        echo "in correct working directory beginning: ./preservica-mark-ingested.sh collection.$COLLECTION.csv now"
        ./preservica-mark-ingested.sh collection.$COLLECTION.csv
        #begin transfer of new collection
    else
        echo "not in correct working directory"
        exit 1
    fi 
}

#restart worker by removing all files and changing status back to nan
refresh_worker() {
    COLLECTION=$1
    WORKER=$2
    #sudo -u karimay rm -rf /bagit/bags/*
    sudo su -c "rm -rf /bagit/bags/*" -s /bin/bash karimay
    if [ $? -ne 0 ]; then
        log_error_exit "error trying to remove content of bags/ directory"
    fi 
    python3 csvUpdate.py $COLLECTION "status" ""
}


#main script
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


#need to have 1 parameter in command line
if [ -z "$1" ]; then
    echo "currently at worker: $WORKER"
    echo "since no collection number entered going into export process automatically"
fi

COLLECTION=$1
FILE="collection.$COLLECTION.csv"
if [ -f "$FILE" ]; then
    echo "$FILE exists, beginning ingest script"
    mark_ingested "$COLLECTION"
    echo "script completed - removing $FILE now"
    rm $FILE
else
    read -p "start transfer process(1) or exit(0): " USER_INPUT
    if [ "$USER_INPUT" = "1" ]; then
        echo "transfer process for collection starting..."
        export_collection "$WORKER"
        #completed, send email ?
        DATE=$(date)
        mail -s "pa-gmworker0$WORKER exportCollection.sh COMPLETE" emv38@pitt.edu <<< "worker $WORKER finished exportCollection at $DATE"
    else
        echo "exiting..."
        exit 0
    fi
fi 