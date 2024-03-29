# BagIt to PAX converter

## About

Purpose: Create PAX based OPEX suitable for use with Incremental Ingest process from BagIt bags exported from Islandora 7.x-1.x.

## Details

The expected input is a directory of BagIt bags, each of which contains digital object files and metadata files.  The BagIt bag structure can be found here: https://wiki.lyrasis.org/display/ISLANDORA/Islandora+BagIt .  Paged and Compound objects will have child objects nested as additional folders under the data directory.

The objects will be ingested into Preservica with a hierarchy drawn from an EAD found in one of the bags (if available) or in a flat structure.  The objects will be named per the DC identifier, and will have metadata files ingested as supplemental digital objects as well.  The DC and MODS metadata will be applied directly to the digital object.

## Configuration

See the `sample.ini` configuration file for details.

## Running

### Requirements

 * Python 3
 * pip requirements.txt
 * lots of free space (your bags will be decompressed and content will be copied, not moved)

### Process

Edit the pitt.ini file to configure the the Preservica, S3, and local settings.

Copy the content to be packaged into a directory within the Source directory indicated by the configuration.

Execute `pitt_pax_v2.py` via Python.  You will be prompted to either create a new package or upload an existing package.

When creating a package, the script will:
* extract any zipped bags found in the Source directory
* copy select content from the Source to the Working directory
* create OPEX/PAX files in the Working directory
* copy the PAX to the Final directory
* delete the Working directory

When uploading a package, the script will:
* copy the PAX from Final to the S3 bucket
* initiate a Preservica API call to start the selected Ingest workflow

## Disclaimer

  THIS SCRIPT IS PROVIDED "AS IS" AND WITHOUT ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, WITHOUT
  LIMITATION, THE IMPLIED WARRANTIES OF MERCHANTIBILITY AND FITNESS FOR A PARTICULAR PURPOSE.

  It is HIGHLY suggested that you test this script in your environment, check the resulting OPEX files BEFORE YOU UPLOAD THEM TO
  PRESERVICA, and ingest a few examples to ensure the OPEX files are appropriate for your needs.
  This is especially important if you are integrating with catalogs where the collection code or other attributes
  may be used to influence catalog sync processes.

## Required workflow id

The script requires a workflow id as part of the configuration, based on the OPEX workflow in your system you would like to use for this project.  If you have access to Manage workflows under the Ingest menu in the UI, you can find this workflow id as the `contextid` querystring parameter when using the "Configure Errors" link.

This id can also be retrieved via API calls.

First, you'll need to authenticate to your system via the following authentication POST call - https://yoursite.preservica.com/api/accesstoken/login (documentation for this call can be found here: [Access Token Documentation](https://demo.preservica.com/api/accesstoken/documentation.html)).

Once authenticated, you will need to submit the following workflow API call: https://yoursite.preservica.com/sdb/rest/workflow/contexts?workflowDefinitionId=com.preservica.core.workflow.ingest.opex.incremental&type=ingest (documentation can be found here: [Preservica Workflow API Documentation](https://demo.preservica.com/sdb/rest/workflow/documentation.html)).

You will be given a list with the name of the OPEX incremental workflows, and the workflow context ID associated. The workflow must be ticked as "active" when you call for the workflow context ID.

NOTE: The OPEX workflow associated with the script needs to be set to Manual, must have "delete from source" ticked, and must have "require manifests" ticked.  The "OPEX Container Directory" in the workflow configuration must match your selection of the "" in the ini.

## License

Written by Kayla Heslin as part of a Preservica Accelerated Success project for the University Library System of the University of Pittsburgh as a work for hire.  The University of Pittsburgh releases this work under a license of GPL 2, or at your option, any later GPL license. 
