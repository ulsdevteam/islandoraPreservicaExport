# islandoraPreservicaExport
Tools to export content from Islandora to Preservica

## bagit-pax
A script to process BagIt bags exported from Islandora, converting them to PAX and then ingesting them to Preservica via OPEX.  See [bagit-pax README](bagit-pax/README.md).

## preservica-mark-exported.sh:
A script to examine BagIt bags exported from Islandora, and then update the associated Islandora object's RELS-EXT datastream with a date of when that export occurred.

This command take no input or parameters, but is dependent on an internal variable (BAGDIR) which must point to the BagIt export directory.  Defaults to `/bagit/bags`

The script will add (or replace) the element of `islandora:preservicaExportDate` to the RELS-EXT with the datetime value of the export time per the Bag's file properties.

## preservica-mark-ingested.sh
A script to examine a download of a Process (Ingest Card) from the Preserica Monitor Processes interface, and then update the associated Islandora object's RELS-EXT datastream with a reference to the Preservica asset Ref.

This command takes a single argument of the path to the downloaded file.

The script will add (or replace) the element of `islandora:preservicaRef` to the RELS-EXT with the value of the Preservica Ref identifier.


## exportCollection.sh 
script to start the exporting a collection on that specific gmworker

takes no input as it runs on the cronjob:
    0 9-19 * * 1-5 /usr/local/bin/cronic /mounts/transient/automation/islandoraPreservicaExport/exportCollection.sh

uses reformatted.csv file to search up current location of gmworker and which collection its on and returns the status

switch case based on worker status:

        - ERROR: refreshed worker and restarts
        - bagit or nan: starting bagit process
        - DC: dc stage
        - exportScript: calls export script
        - Ready: collectio has been exported and waiting for archive03 to start the pittpax process
        - * : other errors will display on the err.log before exiting


## ingestCollection.sh
script to begin the ingest of the collection.*.csv files based on what gmworker they began the export process on 

takes no input using cronjob:
    5 9-19 * * 1-5 /usr/local/bin/cronic /mounts/transient/automation/islandoraPreservicaExport/ingestCollection.sh

runs through all collection.*.csv files and and depending on which ones started in this server - runs the preservica-mark-ingested.sh script

if successful, deletes the collection.csv file and updates the corresponding log

## archiveAutomation.sh
script that starts the export process to preservica using the pittpax python script

takes no input using cronjob:
    

runs through every gm-worker-(0-1) and checks if a collection is ready for export using reformatted.csv

    for every worker:
        if worker status is READY:
            1. start the transfer
            2. run automated pittpax script
            3. remove old collections
            4. assign new collection to worker
        else:
            move onto next worker

## error logs
error logs found at /mounts/transient/automation/err

    format:  DD-MM-YYYY-{hostname}-err.log
    example: 04-15-2025-pa-gmworker-02.library.pitt.edu-err.log

## status logs
status logs for the collection exports found at: /mounts/transient/automation/logs/

    format: {collection number}-{gmworker #}.log
    example: 180-2.log
