#!/bin/bash
# Where is the downloaded API log from Preservica?
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
# Write out an XSL which performs an identity transform on RELS-EXT, removing any existing preservicaExportDate, and adding a new one with the timestamp passed in as a parameter.
cat <<'EOF'> $TMPDIR/update-preservica-ingest.xsl
<xsl:stylesheet version="1.0" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:islandora="http://islandora.ca/ontology/relsext#" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:param name="pref" />
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  <xsl:template match="islandora:preservicaRef" />
  <xsl:template match="rdf:Description">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
      <islandora:preservicaRef><xsl:value-of select="$pref" /></islandora:preservicaRef>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
EOF
# Extract just the PIDs
cut -d',' -f1 $1 | grep '^pitt:' > $TMPDIR/dsio.pids
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
  if [[ $line != "pitt:"* ]]
  then
    continue
  fi
  i=$TMPDIR/rels-ext/`echo $line | cut -d',' -f1`^RELS-EXT.rdf
  PREF=`echo $line | cut -d',' -f2 | tr -d '\n' | tr -d '\r'`
  # Transform the RELS-EXT with our XSLT, adding in the new presericaExportDate
  xsltproc --stringparam pref "$PREF" -o $i $TMPDIR/update-preservica-ingest.xsl $i
  if [[ $? -ne 0 ]]
  then
    >&2 echo "xsltproc failed on $i"
    ERRORFLAG=1
  fi 
done < $MESSAGEFILE
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
