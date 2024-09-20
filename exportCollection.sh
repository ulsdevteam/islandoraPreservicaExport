#!/bin/bash

#script to start collection export 
#./exportCollection.sh "{collection number}"

CSV_FILE='/mounts/transient/automation/reformatted.csv'
LOG_DIR='/mounts/transient/automation/logs'
ERR_DIR='/mounts/transient/automation/err/'

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
    sudo -u karimay drush --uri=https://gamera.library.pitt.edu/ --root=/var/www/html/drupal7/ --user=$USER create-islandora-bag --resume collection pitt:collection.$COLLECTION
    update_log "$COLLECTION" "$WORKER" "drush completed"
}

# $1 is collection
# $2 is worker
DC_creation(){
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "DC starting"
    python3 csvUpdate.py "$COLLECTION" 'status' 'DC'
    sudo -u karimay wget -O /bagit/bags/'DC.xml' https://gamera.library.pitt.edu/islandora/object/pitt:collection.$COLLECTION/datastream/DC/view
    update_log "$COLLECTION" "$WORKER" "DC collected"
}


# $1 is collection
# $2 is worker
export_script(){
    COLLECTION=$1
    WORKER=$2
    update_log "$COLLECTION" "$WORKER" "export script starting"
    python3 csvUpdate.py "$COLLECTION" "status" "exportScript"
    ./preservica-mark-exported.sh
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
    echo "result of check collection: $CHECK_COLLECTION"
    if [ "$CHECK_COLLECTION" = "None" ]; then
        echo "worker hasn't been assigned to a collection yet.. run archive03"
    elif [[ "$CHECK_COLLECTION" =~ ^[0-9]+$ ]]; then
        echo "worker $WORKER is currently in collection $CHECK_COLLECTION"
        COLLECTION=$CHECK_COLLECTION
        #check what stage it is at 
        TRANSFER_STATUS=$(python3 csvUpdate.py 'workerStatus' $WORKER)
    else
        echo "worker $WORKER not assigned to collection "$COLLECTION" but to collection "$CHECK_COLLECTION""
        exit 1
    fi

    case $TRANSFER_STATUS in
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
            ;;
        *)
            echo "error"
            exit 1
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


#main script
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#getting worker number
WORKER="${HOSTNAME##*-}"
WORKER="${WORKER%%.*}"
WORKER="${WORKER#0}" 


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
    else
        echo "exiting..."
        exit 0
    fi
fi 


