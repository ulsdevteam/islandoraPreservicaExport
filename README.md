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
