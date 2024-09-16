#!/bin/bash

#script to start collection export 
#./exportCollection.sh "{collection number}"


CSV_FILE='/mounts/transient/automation/reformatted.csv'
LOG_DIR='/mounts/transient/automation/logs/'
ERR_DIR='/mounts/transient/automation/err/'


#log file
# $1 is collection
# $2 is worker
# $3 is the message written to file
update_log() {
    COLLECTION=$1
    WORKER=$2
    #check if log for that collection already exists
    LOG_FILE=$(ls $LOG_DIR | grep "^$COLLECTION" )
    if [ -z $LOG_FILE ]; then
        echo "log file hasn't been created yet, creating one now"
        LOG_FILE=$LOG_DIR/$COLLECTION-$WORKER.log
        touch $LOG_FILE
    else
        echo "$LOG_FILE already exists, updating now"
        MESSAGE="$(date) - "$3""
        echo $MESSAGE >> "$LOG_DIR"/"$LOG_FILE"
    fi 

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
        echo "worker hasn't been assigned to a collection yet.. assigning now"

        #assign new collection to worker
        COLLECTION=$(python3 csvUpdate.py 'workerAssign' $WORKER)
        update_log "$COLLECTION" "$WORKER" "worker $WORKER assigned to collection $COLLECTION"

        #should already be removed in archive03
        #sudo -u karimay rm /bagit/bags/*

    elif [[ "$CHECK_COLLECTION" =~ ^[0-9]+$ ]]; then
        echo "worker $WORKER is currently in collection $CHECK_COLLECTION"
        COLLECTION=$CHECK_COLLECTION

    else
        echo "worker $WORKER not assigned to collection "$COLLECTION" but to collection "$CHECK_COLLECTION""
        exit 1
    fi

    update_log "$COLLECTION" "$WORKER" "drush starting"
    echo "running worker $WORKER with collection $COLLECTION"

    #update worker with correct collection
    sudo -u karimay drush --uri=https://gamera.library.pitt.edu/ --root=/var/www/html/drupal7/ --user=$USER create-islandora-bag --resume collection pitt:collection.$COLLECTION
    update_log "$COLLECTION" "$WORKER" "drush completed"

    update_log "$COLLECTION" "$WORKER" "collecting DC"
    sudo -u karimay wget -O /bagit/bags/'DC.xml' https://gamera.library.pitt.edu/islandora/object/pitt:collection.$COLLECTION/datastream/DC/view
    update_log "$COLLECTION" "$WORKER" "DC collected"

    #git pull origin
    echo "drush completed, beginning export script"
    update_log "$COLLECTION" "$WORKER" "starting export script"
    ./preservica-mark-exported.sh
    update_log "$COLLECTION" "$WORKER" "completed export script"
    #update status to Ready
    python3 csvUpdate.py $COLLECTION "status" "Ready"

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
    echo "since no collection number entered going into ingest script automatically"
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


