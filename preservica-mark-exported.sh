#!/bin/bash
# Where are the Bags which were exported to Preservica?
if [ "$BAGDIR" == "" ]
then
  BAGDIR=/bagit/bags
fi
# Where can we setup a temporary working directory?
TMPDIR=`mktemp -d`
# Have we seen any errors which require operator intervention?
ERRORFLAG=
# Write out an XSL which performs an identity transform on RELS-EXT, removing any existing preservicaExportDate, and adding a new one with the timestamp passed in as a parameter.
cat <<'EOF'> $TMPDIR/update-preservica-export.xsl
<xsl:stylesheet version="1.0" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:islandora="http://islandora.ca/ontology/relsext#" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:param name="timestamp" />
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>
  <xsl:template match="islandora:preservicaExportDate" />
  <xsl:template match="rdf:Description">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
      <islandora:preservicaExportDate rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime"><xsl:value-of select="$timestamp" /></islandora:preservicaExportDate>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
EOF
# iterate across each Bag which was exported
for i in $BAGDIR/Bag-pitt_*
do
  # find the DC file for this object
  t=`basename $i | sed 's"\.zip$"/data/DC.*"'`
  # find the DC files for any child objects
  s=`basename $i | sed 's"\.zip$"/data/*/DC.*"'`
  # extract the DC to the working directory
  unzip -qd $TMPDIR $i "$t"
  if [[ $? -ne 0 ]]
  then
    >&2 echo "Failed to unzip $t from $i"
    ERRORFLAG=1
  fi
  # optionally, extract the child DCs to the working directory
  unzip -qql $i "$s" > /dev/null
  if [[ $? -eq 0 ]]
  then
    unzip -qd $TMPDIR $i "$s"
    if [[ $? -ne 0 ]]
    then
      >&2 echo "Failed to unzip $s from $i"
      ERRORFLAG=1
    fi
  fi
done
# create a directory where we can store files representing each bagged object, with the timestamp of when the bag was created
mkdir $TMPDIR/Bag-dates
DCFILES=
if compgen -G "$TMPDIR/*/data/DC.*" > /dev/null
then
  DCFILES="$DCFILES "`compgen -G "$TMPDIR/*/data/DC.*"`
fi
if compgen -G "$TMPDIR/*/data/*/DC.*" > /dev/null
then
  DCFILES="$DCFILES "`compgen -G "$TMPDIR/*/data/*/DC.*"`
fi
# iterate across each DC file, writing into a PID list for Datastream CRUD and capturing the timestamp of the original bag
for i in $DCFILES
do
  # extract the PID (dc:identifier, begins with "pitt:")
  PID=`xmllint --xpath '//*[local-name()="identifier" and namespace-uri()="http://purl.org/dc/elements/1.1/" and substring(text(), 1, 5)="pitt:"]/text()' $i 2> /dev/null`
  if [[ $? -eq 0 ]]
  then
    # to find the original Bag name, remove the TEMPDIR prefix, and data suffix
    f=${i#"$TMPDIR/"}
    f=${f%%/data*}
    # Set a file with the modification datetime of the Bag, in a Datastream CRUD naming
    touch -r $BAGDIR/${f}.zip $TMPDIR/Bag-dates/$PID
    # Echo the PID to our list
    echo $PID
  else
    >&2 echo "No PID for $i"
    ERRORFLAG=1
  fi
done > $TMPDIR/dsio.pids
# Fetch the RELS-EXT for each PID in the list
drush -qy --root=/var/www/html/drupal7/ --user=$USER --uri=http://gamera.library.pitt.edu islandora_datastream_crud_fetch_datastreams --pid_file=$TMPDIR/dsio.pids --dsid=RELS-EXT --datastreams_directory=$TMPDIR/rels-ext --filename_separator=^
if [[ $? -ne 0 ]]
then
  >&2 echo "CRUD fetch returned an error"
  ERRORFLAG=1
fi
# Iterate across each RELS-EXT
for i in $TMPDIR/rels-ext/*^RELS-EXT.*
do
  # We wrote this file with the timestamp of the bag earlier; remove the RELS_EXT.ext suffix to find it
  f=`basename $i | sed 's/\^RELS-EXT.*$//'`
  # Find the datestamp on the Bag
  EXPORTED=`date --utc -r $TMPDIR/Bag-dates/${f} "+%FT%T.%3NZ"`
  if [[ "$EXPORTED" = "" ]]
  then
    >&2 echo "Export date is missing for $f"
    ERRORFLAG=1
  else
    # Transform the RELS-EXT with our XSLT, adding in the new presericaExportDate
    xsltproc --stringparam timestamp "$EXPORTED" -o $i $TMPDIR/update-preservica-export.xsl $i
    if [[ $? -ne 0 ]]
    then
      >&2 echo "xsltproc failed on $i"
      ERRORFLAG=1
    fi 
  fi
done
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
