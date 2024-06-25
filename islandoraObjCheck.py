##Function:  pageCount_of_Pid
## readin a pidlist file containing pitt identifiers and process through
## islandora object api request to compute the number of the pids' child  
## objects with the filter 'RELS_EXT_isPageOf_uri_s' on objects' metadata
## Created 06/17/2024
## @author: Ruiling Z.
## @params: file-pids.csv, test-solr-object-3.xml
## @result: mscount.csv

import requests, json, os
import re
import csv
from collections import defaultdict

#locate xml data
from xml.etree import ElementTree as etree

f_path = os.path.dirname(os.path.realpath(__file__)) 
'''
1) api to get islandora object via filter of pageOf attributes
2) dump the objectIDs(PID) with the counts of children records associated to the PIDs

3) preservica report api, similarly get compoundObjectIDs(conceptual objs) counts, and 
   count the associated children members baseon the concptual objectID 
4) validate both parent level and with the kids level

'''
f_pids = "file-pids.csv"
mscount_file="mscount.csv"
def get_islandoraData(s_query):
    #pid format convention
    str_q = "PID:pitt\\" + s_query[4:]
    try:
        #step1). retrieve object from islandora api request
        url ='https://gamera.library.pitt.edu/solr/uls_digital_core/select'
        payload = {"q": str_q,
                "fl":"PID,RELS_EXT_isPageOf_uri_s,RELS_EXT_hasModel_uri_ms",
                "sort":"PID asc", 
                "wt":"json"}

        responses = requests.get(url, params=payload)
        if (responses.status_code ==200) :
            # store json data rest api response 
            json_data = (responses.json())
            results = json_data['response']
            #print (json.dumps(results['docs'], indent=4))
            return (results)
    except requests.exceptions.HTTPError as e:
        print("Error: " + str(e))
#define a dict value with a value of list holding ms_count, and ms_items
ms_items = defaultdict(list)

# step2) Helper function used to compute the multpart objects with the relation mapping of RELS_EXT_isPageOf_uri_s 
# to the pid from the solr api response
def get_multipart_count(objID):
    results = get_islandoraData(objID)
    assert isinstance(results, dict) #make sure the response data is a dict 
    for data in results['docs']:
        tmpPagelst ={}
        tempParentID =""
        #pass the objID to solr to retrieve data from islandora
        if ((data["PID"]) == objID and "RELS_EXT_isPageOf_uri_s" in data):
        
            # extract the parentPID from the pageOf
            tempParentID = data["RELS_EXT_isPageOf_uri_s"].rpartition("/")[2]
            #print("Check2).", objID, " ", data["RELS_EXT_isPageOf_uri_s"], "parentObj: " ,tempParentID)
            
            #first time associate page item to parent
            if not (tempParentID in ms_items.keys()):
                tmpPagelst['pageIds']=[]
                tmpPagelst['pageIds'].append(objID)
                tmpPagelst['counter'] = 1
                ms_items[tempParentID]=tmpPagelst
                print("New key added in ms_items: ", ms_items[tempParentID])
            
            else:
                #update the value for the key matching tempParentID
                v= [v for k,v in ms_items.items() if k == tempParentID]
                v[0]["counter"] += 1 
                v[0]["pageIds"].append(objID)
                #print("after update: ", ms_items[tempParentID])
    return ms_items

#Main Function: takes in csv file containing object IDs, and iterate each ID to check on islandora via solr search
#it outputs a csv file with the number of pageOf items associated with each PID
def pageCount_of_Pid (inFile_pids):
    #open file to read the pids
    with open (os.path.join(f_path, inFile_pids), 'r') as pid_f:
        pidreader = csv.DictReader(pid_f)

        #step3). write output file
        with open(os.path.join(f_path, mscount_file), 'w', newline='') as match_f:
            header_lst = ['PID', 'num_isPageOf_uri_s', 'pageitems']
            f_writer = csv.DictWriter(match_f, fieldnames=header_lst)
            f_writer.writeheader()
            #now interate each objs from response
            for row in pidreader:
                item = row['pitt-pid']
                #print("Check1) passing pid: ", item)
                mydict = get_multipart_count(item)
            if mydict:
                print("Check: final ms_item before writing in file " ,json.dumps(mydict, indent =4)) 
                for k,v in mydict.items():
                    f_writer.writerow({header_lst[0]:k, header_lst[1]:v['counter'],header_lst[2]:v['pageIds']})

pageCount_of_Pid(f_pids)

"""
##testing draft for the version parsing xml: readin a pidlist file containing pitt identifiers and process through
## the object api request response from islandora to compute the number of the pids' child objects with 
## the filter 'RELS_EXT_isPageOf_uri_s' 
## Created 06/13/2024
## @params: file-pids.csv, test-solr-object-3.xml
## @result: mscount.csv
"""
xmlfile ="test-solr-object-3.xml"
tmptree=etree.parse(os.path.join(f_path, xmlfile))
#print(tmptree.getroot().tag)     #response
rootnode =tmptree.getroot()
#print(etree.tostring(rootnode, encoding='utf8').decode('utf8'))


#step2). read a pids input file
#iterate name to locate pid
pid_lst =['pitt:31735070061167','pitt:31735029251976']

def checkObjMs(id_lst):
    ms_dict =dict();
    #open file to read the pids
    with open(os.path.join(f_path, f_pids), 'r') as pid_f:
        pidreader = csv.DictReader(pid_f)

        #step3). write output file
        with open(os.path.join(f_path, mscount_file), 'w', newline='') as match_f:
            header_lst = ['PID', 'num_isPageOf_uri_s']
            f_writer = csv.DictWriter(match_f, fieldnames=header_lst)
            f_writer.writeheader()
    
            #now loop the result to interate each records matching the creteria
            for row in pidreader:
                item = row['pitt-pid']
            # find the match pid under <doc>
                counter =0
                for em in tmptree.findall(".//*[@name='PID']"):
                    if (em.text == item):
                        print("element: ", em.attrib, "value: ", em.text)
                        for ms in tmptree.findall(".//*[@name='RELS_EXT_isPageOf_uri_s']"):
                        #if ms.text.find(em.text) != -1: //find match
                            found = re.search(r'[a-zA-Z]*(pitt)\:{}$'.format(em.text.split(':')[-1]), ms.text)
                            if(found):
                                counter +=1 #have child elements, then find the pid   
                        if counter >0:
                            print("ms element: " + em.text + " child element: " + str(counter) + "\n" )
                        else:
                            print("No child element found in ms element: " + em.text +"\n" )
                        f_writer.writerow({header_lst[0]:em.text.split(":")[-1], header_lst[1]:counter})
#testcall   -PASS           
#checkObjMs(pid_lst)

