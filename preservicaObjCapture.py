###########################################################
##Function:  preservicaObjCapture.py
## process an inputFile containing Islandora Objects'pid,numberOfPage of the Object to valid 
## the associated preservica objects by checking the count of the bitstreams for each preservica 
## object matching the numberOfPage count from the correspondent islandora object
## @params: islandorapids.csv :  file generated from islandoraObjCheck process
## @result: valid_result.csv
###########################################################
import requests, json, csv
from xml.etree import ElementTree as etree
from collections import defaultdict
import sys, os, getopt, array
import subprocess 
import time
import preservicaCheck as token_fn

f_path = os.path.dirname(os.path.realpath(__file__)) 
islandora_count_f = "./output/membercount.csv"
valid_result_f = "./output/valid_result.csv"

st_timer = time.time()
tmp =""
headers = {
    'Preservica-Access-Token': tmp
}

curr_session=[]

sInfoObj_baseUrl = "https://pitt.preservica.com/api/entity/information-objects/"
sContentObj_baseUrl = "https://pitt.preservica.com/api/entity/content-objects/"

InfoObjdata = defaultdict(list)
def getObjInfo(apiUrl):      
    InfoObjdata = defaultdict(list)
    try:
        responses = requests.get(apiUrl, headers=headers)
        responses.raise_for_status()
        xml_response = str(responses.content.decode('UTF-8'))
        
        #process the xml
        entity_response = etree.fromstring(xml_response)
        reference = entity_response.find('.//{http://preservica.com/XIP/v7.2}Ref')
        identifier = entity_response.find('.//{http://preservica.com/EntityAPI/v7.2}Identifiers')
        representation = entity_response.find('.//{http://preservica.com/EntityAPI/v7.2}Representations')
        tmpObjInfo = {}
        tmpObjInfo["PIDInfo"] = identifier.text
        tmpObjInfo["representationInfo"] = representation.text
        InfoObjdata[reference.text] = tmpObjInfo
        
        return InfoObjdata
    except requests.exceptions.RequestException as e:
        print("Error: ", e)
           
#capture all ContentObjects from Representations : dict {objectId: contentids}
def getContentObjID(sRep_Url):
    r = requests.get(sRep_Url, headers=headers)
    counter =0
    contentobjdata ={}
    # store json data rest api
    if (r.status_code == 200):
        xml_resRepresentation = str(r.content.decode('UTF-8'))
        #process the xml
        res_content_response = etree.fromstring(xml_resRepresentation)
        infoObjID = res_content_response.find('.//{http://preservica.com/XIP/v7.2}InformationObject')
        contentobjs = res_content_response.findall('.//{http://preservica.com/XIP/v7.2}ContentObjects/{http://preservica.com/XIP/v7.2}ContentObject')
        tempcontentid =[]
      
        for contentobj in contentobjs:
            #capture all content object ids for the information object  
            tempcontentid.append(contentobj.text)
            contentobjdata[infoObjID.text] = tempcontentid    
        return contentobjdata

#make a generic call to retrieve object data from preservica restapi 
def getcontenobjInfo(sObjbaseUrl, sobjitem="", sParam=""):
    try:
        r = (sobjitem and sParam) and requests.get(f'{sObjbaseUrl}{sParam}/{sobjitem}', headers=headers) or requests.get(f'{sObjbaseUrl}', headers=headers)
        r.raise_for_status()
        xml_responses = str(r.content.decode('UTF-8'))
        res_tree_response = etree.fromstring(xml_responses)
        return res_tree_response
    except requests.exceptions.RequestException as e:
        print("Error: ", e)

#capture the generations of contentobject id
def getbitstreamInfo(sContentGen, sRefId):
    res_gen = getcontenobjInfo(sContentObj_baseUrl, sContentGen , sRefId)
    genLst = res_gen.findall('.//{http://preservica.com/EntityAPI/v7.2}Generations/{http://preservica.com/EntityAPI/v7.2}Generation[@active ="true"]')
    
    contBitstream = defaultdict(list)
    total = 0
    #iterate generation to get the bitstream count
    for ele in genLst:
        bitstreamLst = getcontenobjInfo(ele.text).findall('.//{http://preservica.com/XIP/v7.2}Bitstreams/{http://preservica.com/XIP/v7.2}Bitstream')
        total += len(bitstreamLst)
    contBitstream[sRefId] = total
    return contBitstream
          
#retrieves all representations of InformationObj and compute total bitstreams underneath contentObjs for the representation
def getRepresentionInfo(sUrl, sRef_ID):
    stempUrl = sUrl + sRef_ID
    testInfoObj = getObjInfo(stempUrl)
    if len(testInfoObj) > 0:
        try:
            sRepUrl = next(iter(testInfoObj.values()))['representationInfo']
            req_Rep = requests.get(sRepUrl, headers=headers)
            req_Rep.raise_for_status()
            xml_reqRep = str(req_Rep.content.decode('UTF-8')) 
            representation_rep = etree.ElementTree(etree.fromstring(xml_reqRep))
            representations = representation_rep.findall(
                './/{http://preservica.com/EntityAPI/v7.2}Representations/{http://preservica.com/EntityAPI/v7.2}Representation'
            )
            contentObj_lst ={}
            BitstreamCount =0
            for representation in representations:
                #print(representation.text, " ", representation.attrib)
                
                #get all content object IDs for each of the represention
                listOfRepresentContent = getContentObjID(representation.text)
                
                if len(listOfRepresentContent) > 0 : #get value of the first key since only one element
                    #iterate each contentObj to get its generations for computing bitstreams
                    for co in listOfRepresentContent.values():
                        if len(co) > 0:
                            for i in co:
                               BitstreamCount += getbitstreamInfo("generations", i)[i]
                    #print("Total bitstream for :" ,next(iter(listOfRepresentContent)), "is ", BitstreamCount)

                    if not (next(iter(listOfRepresentContent)) in contentObj_lst.keys()):   
                        contentObj_lst[next(iter(listOfRepresentContent))] = BitstreamCount
                    else:
                        contentObj_lst[next(iter(listOfRepresentContent))] += BitstreamCount
            #this should be the total bitstreams under the InformationObject
            return (contentObj_lst)    
        except requests.exceptions.RequestException as e:
            print("Error: ", e)  

#match the count, if match update the xml, otherwise output log error
def preservica_bitstream_valid (f_in):
    #open file to read the output file from islandoraObjcheck eg. mscount.csv)
    with open (os.path.join(f_path, f_in), 'r', newline='') as islandoraCount_f:
        csvreader = csv.DictReader(islandoraCount_f)
        
        with open(os.path.join(f_path, valid_result_f), 'w', newline='') as result_f:
            header_lst = ['PID', 'islandora_count', 'preservica_refID', 'bitstreamCount']
            f_writer = csv.DictWriter(result_f, fieldnames=header_lst)
            f_writer.writeheader()
            #now iterate each objs from response
            global st_timer, curr_session
            
            for row in csvreader:
                #add logic to check token expiration before access preservica apis
                #print(f"usage:  {(time.time()-st_timer)*10**3:.02f} ms", curr_session)
                if (round((time.time()-st_timer)*10**3) - 600000 >0 ):  
                   new_session = token_fn.getRefreshToken(curr_session)
                   curr_session[0]= new_session[0]
                   curr_session[1] =new_session[1]
                   headers['Preservica-Access-Token']= new_session[0]
                   st_timer = time.time()
                
                bitstream_dict ={}
                bitstream_dict = getRepresentionInfo(sInfoObj_baseUrl, row['preservica_refID']) 
                if bitstream_dict:
                    for k,v in bitstream_dict.items():
                        if v == int(row['num_isPageOf_uri_s']):
                            f_writer.writerow({header_lst[0]:row['PID'], header_lst[1]:row['num_isPageOf_uri_s'],
                                           header_lst[2]:k, header_lst[3]:v})
                            print("ObjectID: ", row['PID'] , "membercounts is matched ")
                        else:
                            tmp = "Mismatch-" + str(v)
                            f_writer.writerow({header_lst[0]:row['PID'], header_lst[1]:row['num_isPageOf_uri_s'],
                                           header_lst[2]:k, header_lst[3]:tmp})
                            print("ObjectID: ", row['PID'] , " membercounts is not matched ")
        
if __name__ == "__main__": 
    curr_session = token_fn.generateToken()
    print("token :" ,curr_session[0], " refresh-token: ", curr_session[1])
    headers['Preservica-Access-Token'] = curr_session[0]
    st_timer = time.time()
    preservica_bitstream_valid(islandora_count_f)
    
    

