#!/bin/bash
# Where is the ingest monitor message file downloaded from Preservica?
MESSAGEFILE=$1
if [ "$MESSAGEFILE" == "" ]
then
  >&2 echo "USAGE: $0 <filename>"
  exit 1
fi
# Where can we setup a temporary working directory?
TMPDIR=`mktemp -d`
# Have we seen any errors which require operator intervention?
ERRORFLAG=

# Write out an XSL which restores the original state of RELS-EXT
cat <<'EOF'> $TMPDIR/undo-preservica-ingest.xsl
<xsl:stylesheet version="1.0" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:islandora="http://islandora.ca/ontology/relsext#" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:param name="pref" />
  
  
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  
  <!-- removing preservicaRef line -->
  <xsl:template match="islandora:preservicaRef" />
  
  
  <xsl:template match="rdf:Description">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
      
      <islandora:preservicaExportDate>
        <xsl:value-of select="$pref" />
      </islandora:preservicaExportDate>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
EOF

# Use a python script to extract the fifth (islandora identifier) and sixth (preservica identifier) columns from the CSV
cat <<'EOF'> $TMPDIR/extract-identifiers.py
import sys
import csv
with open(sys.argv[1], 'r') as csvfile:
  linereader = csv.reader(csvfile)
  for line in linereader:
    if line[4].startswith('pitt:'):
      print(line[4] + '|' + line[5])
EOF
python $TMPDIR/extract-identifiers.py $MESSAGEFILE > $TMPDIR/id-pairs.pipe

# Extract just the PIDs
cut -d'|' -f1 $TMPDIR/id-pairs.pipe > $TMPDIR/dsio.pids
mkdir $TMPDIR/rels-ext

# Fetch the RELS-EXT for each PID in the list
drush -qy --root=/var/www/html/drupal7/ --user=$USER --uri=http://gamera.library.pitt.edu islandora_datastream_crud_fetch_datastreams --pid_file=$TMPDIR/dsio.pids --dsid=RELS-EXT --datastreams_directory=$TMPDIR/rels-ext --filename_separator=^
if [[ $? -ne 0 ]]
then
  >&2 echo "CRUD fetch returned an error"
  ERRORFLAG=1
fi

# Iterate across each PID
while read -r line
do
  i=$TMPDIR/rels-ext/`echo $line | cut -d'|' -f1`^RELS-EXT.rdf
  PREF=`echo $line | cut -d'|' -f2`
  
  # Transform the RELS-EXT with our XSLT, removing the preservicaRef and restoring preservicaExportDate
  xsltproc --stringparam pref "$PREF" -o $i $TMPDIR/undo-preservica-ingest.xsl $i
  
  if [[ $? -ne 0 ]]
  then
    >&2 echo "xsltproc failed on $i"
    ERRORFLAG=1
  fi 
done < $TMPDIR/id-pairs.pipe

# Ensure no errors were caught before continuing
if [[ "$ERRORFLAG" = "" ]]
then
  # Push the updated RELS-EXT datastreams via Datastream CRUD
  drush -qy --root=/var/www/html/drupal7/ --user=$USER --uri=http://gamera.library.pitt.edu islandora_datastream_crud_push_datastreams --datastreams_mimetype='application/rdf+xml' --datastreams_source_directory=$TMPDIR/rels-ext --no_derivs --filename_separator=^
  if [[ $? -ne 0 ]]
  then
    >&2 echo "CRUD push returned an error"
    ERRORFLAG=1
  fi
else
  >&2 echo 'Datastream CRUD push was not run.'
fi

# Only delete the working directory if there were no errors
if [[ "$ERRORFLAG" = "" ]]
then
  rm -rf $TMPDIR
else
  >&2 echo "Examine $TMPDIR for errors"
  exit 2
fi