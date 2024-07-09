##########################################################
## The file processes an inputFile containing Object PID with its membercontent count from islandora
## and the bitstreams count for the same object from preservica. It then iterates PIDs with the matched
## membercount and update the corresponding rdf file by adding the count 
## value to a new field 'preservicaChildCount'. The last step is to 
## drush push the updated rdf files to islandora
## @params: valid_result_f
## @result: update_extfiles/.rdf files
###########################################################
import sys, os, csv, shutil
from xml.etree import ElementTree as etree
from xml.etree.ElementTree import Element, SubElement
import subprocess,fnmatch 
from pprint import pprint

f_path = os.path.dirname(os.path.realpath(__file__)) 
curr = os.getcwd()
user = os.environ['USER'] if os.getenv("USER") is not None else os.environ['USERNAME']

valid_result_f = "./output/valid_result.csv" 
f_output = "./output/temp_pid.csv"
extRel_fpath =  "/output/extfiles"  
update_fpath = "/output/update_extfiles"
 
#1. create a temp pidsFile holding the verified the bitstreams count for the corresponding perservica obj
##  result: f_output/temp_pid.csv
def getVerifiedPids(f_pids):
    header_fields=["PID"]
    with open (os.path.join( f_path, f_pids ), 'r', newline='') as pids_f:
        csvreader = csv.DictReader(pids_f)
        with open(os.path.join(f_path, f_output), 'w', newline='') as temp_f:
            csvwriter = csv.DictWriter(temp_f, fieldnames=header_fields)
            for r in csvreader:
                if (r["bitstreamCount"]):  # verified the match
                    csvwriter.writerow({header_fields[0]:r["PID"]})

#2.Iterate the intake pids and extract the ext-rel file via drush from islandora
# and export the original rdf files to the designed output directory
def drushfetchDatastream(): 
    pidtest_name = os.path.join(f_path, f_output)
    try:
        subprocess.check_call (['drush', '--root=/var/www/html/drupal7/', '--user={}'.format(user), \
    '--uri=http://gamera.library.pitt.edu', 'islandora_datastream_crud_fetch_datastreams', '--dsid=RELS-EXT', \
    '--pid_file={}'.format(pidtest_name), '--datastreams_directory={}{}'.format(curr, extRel_fpath), '--filename_separator=^', '-y'])
   
    except subprocess.CalledProcessError as e: 
	    print(f"Command failed with return code {e.returncode}")

#3. helper function to update the xml
def fileProcess(fname, ele_name, ele_val):
    #updatefiles in updated_file dir
    curr_file = curr + extRel_fpath + "/" + fname

    #register ns to reserve the original prefix
    ns_dict =dict([node for _,node in etree.iterparse(curr_file, events=['start-ns'])])
    #pprint(ns_dict)
    etree.register_namespace('', 'http://digital.library.pitt.edu/ontology/relations#')
    etree.register_namespace('fedora', 'info:fedora/fedora-system:def/relations-external#')
    etree.register_namespace('fedora-model', 'info:fedora/fedora-system:def/model#')
    etree.register_namespace('islandora', 'http://islandora.ca/ontology/relsext#')
    etree.register_namespace('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')

    curr_tree = etree.parse(curr_file)
    curr_root =curr_tree.getroot()
    #add new tag "preservicaChildCount"
    desc_element = curr_root.find('rdf:Description', ns_dict)
    newNode =etree.SubElement(desc_element, etree.QName(ns_dict["islandora"], ele_name))
    newNode.text =ele_val
    updated_file = curr + update_fpath + "/" + fname
    curr_tree.write( updated_file, "UTF-8")

#4. process an inputFile generated from preservicaObjCapture and add a new tag 
#   RELS_EXT_preservicaChildCount_literal_s to pid's rdf
#   @param: filename: islandora-preservica-bitstream matched pidfile
#   @param: filepath: file dir to host the extl-rel generated from fname pids via drush
#   @param: elementName: new element tagName designed to be added

def updateExtRelFile(fpath, fname, e_name):
    with open (os.path.join( f_path, fname ), 'r', newline='') as pf:
        csvreader = csv.DictReader(pf)
        for r in csvreader:
            if (r["bitstreamCount"]):  # pid with the verified countmatch
                    #find the ext file matching the name r['PID'], might use re
                    tmp_pattern = r['PID'] + "^RELS-EXT.rdf"
                    for file in os.listdir(curr+fpath):
                        if fnmatch.fnmatch(file, tmp_pattern):
                            print(file)
                            fileProcess(file, e_name, r["bitstreamCount"]) 

#5. push modified .rdf to islandora via drush
def drushpushDatastreams(): 
    try:
        subprocess.check_call (['drush', '--root=/var/www/html/drupal7/', '--user={}'.format(user), \
    '--uri=http://gamera.library.pitt.edu', 'islandora_datastream_crud_push_datastreams', '--no_derivs', \
    '--update_dc=0', '--datastreams_source_directory={}/output/update_extfiles'.format(curr), '--filename_separator=^', '-y'])
   
    except subprocess.CalledProcessError as e: 
	    print(f"Command failed with return code {e.returncode}")

if __name__ == "__main__": 
    getVerifiedPids(valid_result_f) 
    drushfetchDatastream() 
    
    ##copy all the file in an update_fpath to use for testing purpose
    org_files = os.listdir(curr+extRel_fpath)
    shutil.copytree(curr+extRel_fpath, curr+update_fpath)

    newTagName = "preservicaChildCount" 
    updateExtRelFile(update_fpath, valid_result_f,newTagName)
    #drushpushDatastreams()

  
