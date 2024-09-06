#!/bin/bash

#script to start collection export 
#./exportCollection.sh "{collection number}"

CSV_FILE='/mounts/transient/automation/reformatted.csv'

#calling other gmworkers through this script?

#export collection
#1st parameter is collection number
export_collection() {
    COLLECTION=$1
    echo "collection number = $COLLECTION at $PWD"

    #check if worker is already assigned
    COLLECTION_NUMBER=$(python csvUpdate.py 'workerFind' '4')
    if [ "$COLLECTION_NUMBER" = "NULL" ]; then
        echo "worker hasn't been assigned "$COLLECTION" yet.. assigning now"
        python csvUpdate.py "$COLLECTION" 'worker' '4'

        #should already be removed in archive03
        sudo -u karimay rm /bagit/bags/*

    elif [ "$COLLECTION" = "$COLLECTION_NUMBER" ]; then
        echo "worker 4 is currently in collection $COLLECTION_NUMBER"
        #check if already ready   
    else
        echo "worker 4 not assigned to collection "$COLLECTION" but to collection "$COLLECTION_NUMBER""
        exit 1
    fi

    #update worker with correct collection
    #python csvUpdate.py "$COLLECTION" "worker" "4"
    sudo -u karimay drush --uri=https://gamera.library.pitt.edu/ --root=/var/www/html/drupal7/ --user=$USER create-islandora-bag --resume collection pitt:collection.$COLLECTION

    sudo -u karimay wget -O /bagit/bags/'DC.xml' https://gamera.library.pitt.edu/islandora/object/pitt:collection.$COLLECTION/datastream/DC/view

    #git pull origin
    ./preservica-mark-exported.sh
    #update status to Ready
    python csvUpdate.py $COLLECTION "status" "Ready"

}

mark_exported(){
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

#check to see if the drush command was already started - if so, don't remove items in bagit/bags/


#find a collection number that has a 1 in the include and no worker assigned to it yet


#main script
#--------

#need to have 1 parameter in command line
if [ -z "$1" ]; then
    echo "need to enter collection number on command line"
    exit 1
fi 

#check if opex log exists, 
COLLECTION=$1
FILE="collection.$COLLECTION.csv"
if [ -f "$FILE" ]; then
    echo "$FILE exists, beginning ingest script"
    mark_exported "$COLLECTION"
else
    read -p "$FILE not found, starting transfer process(1) or exit(0): " USER_INPUT
    if [ "$USER_INPUT" = "1" ]; then
        echo "transfer process for collection $COLLECTION starting..."
        export_collection "$COLLECTION"
    else
        echo "exiting..."
        exit 1
    fi
fi 


