##Function:  pageCount_of_Pid
## readin a pidlist file containing pitt identifiers and process through
## islandora object api request to compute the number of the pids' child  
## objects with the filter 'RELS_EXT_isPageOf_uri_s' on objects' metadata
## @params: file_pids
## @result: file_PgCount

import requests, json, os
import csv
import subprocess 
from collections import defaultdict

f_path = os.path.dirname(os.path.realpath(__file__)) 
file_pids = "./input/file-pids.csv"   #intakes pidfile
file_pgCount="./output/membercount.csv" 

#retrieve Object and its pageOf members from islandora 
def get_islandoraData(s_query):
    #pid format convention
    q_par = "PID:pitt\\" + s_query[4:]
    q_pages = "RELS_EXT_isPageOf_uri_s: info\\:fedora\\/pitt\\" + s_query[4:] + " OR " + q_par
    try:
        #step1). retrieve object from islandora api request
        url ='https://gamera.library.pitt.edu/solr/uls_digital_core/select'
        payload = {"q": q_pages,
                "fl":"PID,RELS_EXT_isPageOf_uri_s,RELS_EXT_hasModel_uri_ms,RELS_EXT_preservicaRef_literal_s",
                "sort":"PID asc",
                "rows":"100000",
                "wt":"json"}

        responses = requests.get(url, params=payload)
        if (responses.status_code ==200) :
            json_data = (responses.json())
            results = json_data['response']
            #print(json.dumps(ms_items, indent=4))
            return (results)
    except requests.exceptions.HTTPError as e:
        print("Error: " + str(e))

#define a dict value with a value of list holding islandora object and its pageOf count
ms_items = defaultdict(list)

# Helper function to compute the multpart objects via the relation mapping
# 'RELS_EXT_isPageOf_uri_s' to the Object PID from solr api response
def get_multipart_count(objID):
    results = get_islandoraData(objID)
    numOfpages = results['numFound']
    s_preservicaRef ="" 
    #make sure the response data is a dict
    assert isinstance(results, dict) 
   
    for data in results['docs']:
        tmpPagelst = defaultdict(list)
        #capture the preservica reference ID associated to the ObjectID, if existing
        if ( "RELS_EXT_preservicaRef_literal_s" in data):
            s_preservicaRef = data["RELS_EXT_preservicaRef_literal_s"]
            numOfpages -=1   #exclude parent Object

        #pass objID to solr to retrieve childcontent from islandora
        if ("RELS_EXT_isPageOf_uri_s" in data):
            #retrieve parent object associated
            uri_obj = data["RELS_EXT_isPageOf_uri_s"].split("/")[-1]
            if not ( uri_obj in ms_items.keys()):      
                tmpPagelst['counter'] = 1
                ms_items[uri_obj]=tmpPagelst
            else:
                #update the value for the key matching object ID
                v= [v for k,v in ms_items.items() if k == uri_obj]
                v[0]["counter"] += 1 
           
    #export the associated preservica reference ID if existing           
    if (s_preservicaRef):
        val = [val for keyId, val in ms_items.items() if keyId==objID]
        if val:
            val[0]['preservica_RefID'] = s_preservicaRef

    return ms_items

# Main Function: takes in PIDfile in the format {PID}. It iterates pids to check on islandora via 
# solr search, and outputs a csv file containing total# of the Object's pageOf items from islandora, and 
# preservica referenceID associated to the pid, if exising
def pageCount_of_Pid (inFile_pids):
    with open (os.path.join(f_path, inFile_pids), 'r') as pid_f:
        pidreader = csv.reader(pid_f)
        
        #write output file
        with open(os.path.join(f_path, file_pgCount), 'w', newline='') as match_f:
            header_lst = ['PID', 'num_isPageOf_uri_s', 'preservica_refID']
            f_writer = csv.writer(match_f, delimiter=',')
            f_writer.writerow(header_lst)
            #now iterate each objs from response
            for row in pidreader:
                mydict = get_multipart_count(row[0])  
                
            if mydict:
                for k,v in mydict.items():
                    f_writer.writerow([k, v['counter'], v['preservica_RefID']])
                
def drushfetchPids(): 
    file_name = os.getcwd() +"/input/file-pids.csv"
    user = os.environ['USER'] if os.getenv("USER") is not None else os.environ['USERNAME']
    squery = 'RELS_EXT_preservicaRef_literal_s:* ' 
    squery += 'AND (RELS_EXT_hasModel_uri_ms:info\:fedora/islandora\:manuscriptCModel OR RELS_EXT_hasModel_uri_ms:info\:fedora/islandora\:newspaperIssueCModel OR RELS_EXT_hasModel_uri_ms:info\:fedora/islandora\:bookCModel)'
    squery += 'AND NOT RELS_EXT_preservicaChildCount_literal_s:*'
   
    try:
        s = subprocess.check_call (['drush', '--root=/var/www/html/drupal7/', '--user={}'.format(user), \
    '--uri=http://gamera.library.pitt.edu', 'islandora_datastream_crud_fetch_pids',  \
    '--solr_query={}'.format(squery), '--pid_file={}'.format(file_name)])
        
    except subprocess.CalledProcessError as e: 
	    print(f"Command failed with return code {e.returncode}")

if __name__ == "__main__":
    drushfetchPids()
    pageCount_of_Pid(file_pids)