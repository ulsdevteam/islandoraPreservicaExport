## Description
islandora-preservica-validation process is to compare islandora objects's pagemember count with the corresponding preservica objects's bitstreams count. Islandora Object is validated if the counts are matched, and the islandora object's rdf is to updated by adding new element with the value of the number of count. 

### Requirements
 * Python 3.12
 * pip requirements.txt

### Process
* execute islandoraObjCheck.py to retrieve all islandora objects needed. It will generates an outputfile containing objectID and objects' page membercount and the corresponding preservics object reference Ids 
* execute preservicaObjCapture.py to valide the bitstreams count from preservica with islandora. It will prompt user to use the preservica login credentials in order to generate preservica RESTful APIs
* execute rdfUpdate.py to update the rdfs for the validated islandora objects and drush to push back the updaexecute rdfUpdate.py to update the rdfs for the validated islandora objects and drush to push back the updates to islandora

## Disclaimer

  THIS SCRIPT IS PROVIDED "AS IS" AND WITHOUT ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, WITHOUT
  LIMITATION, THE IMPLIED WARRANTIES OF MERCHANTIBILITY AND FITNESS FOR A PARTICULAR PURPOSE.

