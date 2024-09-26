import os
from lxml import etree as ET
import shutil
import hashlib
import re
from datetime import datetime
from zipfile import ZipFile
import configparser
import logging
from pathlib import Path
import requests
import time
import sys
import lxml
import threading
import boto3
import botocore
from concurrent.futures import ThreadPoolExecutor, as_completed

#boolean to decide whether script will be automatic or not
isAutomated = False
global first_step
global c_f_input
global send_to_s3

#check three parameters to make sure values are correct
def checkParameters(first_step, c_f_input, send_to_s3):
    if first_step != "1" and first_step != "2":
        print("first paramter needs to be 1 or 2")
        return False
    if c_f_input != "ALL" and c_f_input != "QUIT" and not c_f_input.isdigit():
        print("second paramter needs to specify which containers (ALL,1,2,3,QUIT)")
        return False
    if send_to_s3 != "1" and send_to_s3 != "0":
        print("third param needs to be 1 or 0")
        return False
    return True

if len(sys.argv) != 4: print("running script without parameters means input will be required later on")
else:
    first_step = sys.argv[1]
    c_f_input = sys.argv[2]
    send_to_s3 = sys.argv[3] 
    isAutomated = checkParameters(first_step, c_f_input, send_to_s3)
    if isAutomated is True: print("running automatic script with parameters provided")
    else: print("paramters provided not correct, running interactive script")

class ProgressPercentage(object):
  global prog_val

  def __init__(self, filename):
    self._filename = filename
    self._size = float(os.path.getsize(filename))
    self._seen_so_far = 0
    self._lock = threading.Lock()

  def __call__(self, bytes_amount):
    with self._lock:
      self._seen_so_far += bytes_amount
      percentage = (self._seen_so_far / self._size) * 100
      sys.stdout.write(
        "\r%s  %s / %s  (%.2f%%)" % (
          self._filename, self._seen_so_far, self._size,
          percentage))
      sys.stdout.write("\n" + "\n")
      sys.stdout.flush()

      prog_val = "\r%s  %s / %s  (%.2f%%)" % (self._filename, self._seen_so_far, self._size, percentage)
        

def fTime():
    query_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return query_time


def sanitize_working_area(masterdir, folder_name):
    if os.path.exists(os.path.join(masterdir, folder_name)):
        shutil.rmtree(os.path.join(masterdir, folder_name))


def new_token(username, password, basename):
    headers1 = {'accept': 'application/json'}  # define headers for initial request
    credentials = {'username': username,
                   'password': password}  # create credential dictionary. Password has been redacted
    baseURL = 'https://' + basename  # define base API url and save as variable to limit retyping later
    auth = requests.post(baseURL + '/api/accesstoken/login', headers=headers1,
                         data=credentials).json()  # request an API access token
    root_logger.info(auth)
    session = auth['token']  # save token in a variable to be accessed later
    headers = {'Preservica-Access-Token': session,
               'Content-Type': 'application/xml'}  # create new headers for all subsequent requests containing token
    return headers


def fv6Checksum(file_path, sum_type):
    root_logger.debug("fv6Checksum")
    sum_type = sum_type.replace("-", "")
    if sum_type.lower() == "md5":
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5()
            chunk = f.read(8192)
            while chunk:
                file_hash.update(chunk)
                chunk = f.read(8192)
        root_logger.debug("fv6Checksum : file_path " + str(file_path))
        root_logger.debug("fv6Checksum : hash " + file_hash.hexdigest())
        return file_hash.hexdigest()
    elif sum_type.lower() == "sha1":
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha1()
            chunk = f.read(8192)
            while chunk:
                file_hash.update(chunk)
                chunk = f.read(8192)
        root_logger.debug("fv6Checksum : file_path " + str(file_path))
        root_logger.debug("fv6Checksum : hash " + file_hash.hexdigest())
        return file_hash.hexdigest()
    elif sum_type.lower() == "sha256":
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256()
            chunk = f.read(8192)
            while chunk:
                file_hash.update(chunk)
                chunk = f.read(8192)
        root_logger.debug("fv6Checksum : file_path " + str(file_path))
        root_logger.debug("fv6Checksum : hash " + file_hash.hexdigest())
        return file_hash.hexdigest()
    elif sum_type.lower() == "sha512":
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha512()
            chunk = f.read(8192)
            while chunk:
                file_hash.update(chunk)
                chunk = f.read(8192)
        root_logger.debug("fv6Checksum : file_path " + str(file_path))
        root_logger.debug("fv6Checksum : hash " + file_hash.hexdigest())
        return file_hash.hexdigest()


def fCreateOpexFragment(list_folders_in_dir, list_files_in_dir, LegacyXIP,
                        Identifiers_biblio, Identifiers_catalog, source_ID, security_tag, ref_fldr_title, ref_fldr_desc,
                        opex_desc_metadata, file_checksum_dict):
    sub_r = "fCreateOpexFragment"
    root_logger.debug(sub_r)

    ## Opex metadata structure
    OPEX_namespaces = 'http://www.openpreservationexchange.org/opex/v1.2'  # define your namespace
    opex = '{%s}' % OPEX_namespaces
    opex_nsmap = {'opex': 'http://www.openpreservationexchange.org/opex/v1.2'}
    opex_root = ET.Element(opex + 'OPEXMetadata', nsmap=opex_nsmap)

    # Opex Transfer
    opex_transfer = ET.SubElement(opex_root, opex + 'Transfer')

    ##Opex SourceID
    if source_ID == "":
        opex_sourceID = ET.SubElement(opex_transfer, opex + 'SourceID')
        opex_sourceID.text = ref_fldr_title
        opex_source = opex_sourceID.text
    else:
        opex_sourceID = ET.SubElement(opex_transfer, opex + 'SourceID')
        opex_sourceID.text = source_ID
        opex_source = opex_sourceID.text

    ## Opex_Fixity
    if file_checksum_dict == {} or file_checksum_dict == '':
        pass
    else:
        opex_fixity_element = ET.SubElement(opex_transfer, opex + 'Fixities', nsmap=opex_nsmap)
        for k, v in file_checksum_dict.items():
            ET.SubElement(opex_fixity_element, opex + 'Fixity', {'path': k, 'type': 'SHA-1', 'value': v},
                          nsmap=opex_nsmap)

    ## Opex_Manifest
    opex_manifest_element = ET.SubElement(opex_transfer, opex + 'Manifest')
    if list_files_in_dir == [] and list_folders_in_dir == []:
        pass
    else:
        if list_folders_in_dir != []:
            opex_folders = ET.SubElement(opex_manifest_element, opex + 'Folders')
            for lfd in range(len(list_folders_in_dir)):
                opex_folder = ET.SubElement(opex_folders, opex + 'Folder')
                opex_folder.text = list_folders_in_dir[lfd]
                root_logger.debug("fCreateFolderOpexFragments 4 : opex_data_folder " + opex_folder.text)
        if list_files_in_dir != []:
            opex_files = ET.SubElement(opex_manifest_element, opex + 'Files')
            for lff in range(len(list_files_in_dir)):
                if os.path.splitext(list_files_in_dir[lff])[1] == ".opex":
                    opex_file = ET.SubElement(opex_files, opex + 'File', {'type': 'metadata'})
                    opex_file.text = list_files_in_dir[lff]
                else:
                    opex_file = ET.SubElement(opex_files, opex + 'File', {'type': 'content'})
                    opex_file.text = list_files_in_dir[lff]
                root_logger.debug("fCreateFolderOpexFragments 5 : opex_data_file " + opex_file.text)

    # Opex Properties
    opex_properties = ET.SubElement(opex_root, opex + 'Properties')

    ## Opex_title
    if ref_fldr_title == "":
        pass
    else:
        opex_title = ET.SubElement(opex_properties, opex + 'Title')
        opex_title.text = ref_fldr_title

    ## Opex_Description
    if ref_fldr_desc == "":
        pass
    else:
        opex_description = ET.SubElement(opex_properties, opex + 'Description')
        opex_description.text = ref_fldr_desc

    ## Opex Security Tag
    opex_sectag = ET.SubElement(opex_properties, opex + 'SecurityDescriptor')
    opex_sectag.text = security_tag

    # Opex_DescriptiveMetadata

    if opex_desc_metadata == "" and LegacyXIP == "":
        pass
    else:
        desc_metadata = ET.SubElement(opex_root, opex + 'DescriptiveMetadata')
        if LegacyXIP != "":
            LegacyXIP = ET.SubElement(desc_metadata, 'LegacyXIP', {'xmlns': 'http://preservica.com/LegacyXIP'})
            access_ref = ET.SubElement(LegacyXIP, 'AccessionRef')
            access_ref.text = 'catalog'
        else:
            pass
        if opex_desc_metadata != '':
            if type(opex_desc_metadata) == list:
                for descriptive_metadata in opex_desc_metadata:
                    try:
                        opex_descrip_meta_desc = desc_metadata.append(descriptive_metadata)
                    except TypeError:
                        pass
            else:
                opex_descrip_meta_desc = desc_metadata.append(opex_desc_metadata)

    opex_master = ET.tostring(opex_root).decode('utf-8')
    root_logger.info(ref_fldr_title)
    root_logger.info(opex_master)
    root_logger.debug("fCreateOpexFragment : opex master " + str(opex_master))
    parser = ET.XMLParser(remove_blank_text=True)
    opex_xml = ET.fromstring(opex_master, parser=parser)
    new_opex_xml = ET.tostring(opex_xml, encoding="unicode", pretty_print=True)
    # validate xml
    # xmlschema_doc = ET.parse('OPEX-Metadata.xsd')
    # xmlschema = ET.XMLSchema(xmlschema_doc)
    # if xmlschema.validate(opex_xml):
    #     root_logger.info("fCreateOpexFragment : Metadata is valid")
    # else:
    #     root_logger.warning("fCreateOpexFragment : Metadata validation failed for " + str(opex_master))
    return new_opex_xml


def fCreateFolderOpexFragments(folder_path, security_tag):
    collection_desc.clear()
    Identifiers_biblio = ""
    Identifiers_catalog = ""
    LegacyXIP = ""

    opex_fol = folder_path
    parent_dir = opex_fol.split(os.sep)[0:len(opex_fol.split(os.sep)) - 1][-1]
    root_logger.info(parent_dir)
    if os.path.isdir(opex_fol):
        LegacyXIP = ""
        Identifiers_catalog = ""
        ref_fldr_title = opex_fol.split(os.sep)[-1]
        ref_fldr_desc = ''
        if opex_fol.split(os.sep)[-1].lower().startswith('collection'):
            source_ID = ref_fldr_title
        else:
            source_ID = parent_dir + ', ' + ref_fldr_title

        metadata_file = os.path.join(opex_fol, opex_fol.split(os.sep)[-1] + '_' + 'DC.xml')
        ead_file = os.path.join(opex_fol, opex_fol.split(os.sep)[-1] + '_' + 'EAD.xml')
        mods_file = os.path.join(opex_fol, opex_fol.split(os.sep)[-1] + '_mods.xml')
        if os.path.isfile(metadata_file):
            collection_desc.append(fGetDescriptiveMetadata(metadata_file))
            os.remove(metadata_file)
        if os.path.isfile(ead_file):
            collection_desc.append(fGetDescriptiveMetadata(ead_file))
            os.remove(ead_file)
        if os.path.isfile(mods_file):
            collection_desc.append(fGetDescriptiveMetadata(mods_file))
            os.remove(mods_file)
        if collection_desc != []:
            opex_desc_metadata = collection_desc
        else:
            opex_desc_metadata = ''

        list_folders_in_dir.clear()
        list_files_in_dir.clear()
        file_checksum_dict = ''
        opex_file_name = os.path.basename(opex_fol) + ".opex"
        temp_opex_file = os.path.join(opex_fol, opex_file_name)
        for child in os.listdir(opex_fol):
            if os.path.isdir(os.path.join(opex_fol, child)):
                list_folders_in_dir.append(child)
            if os.path.isfile(os.path.join(opex_fol, child)):
                list_files_in_dir.append(child)
        root_logger.info('list of files: ' + str(list_files_in_dir))
        xml_package = ""

        xml_package = fCreateOpexFragment(list_folders_in_dir, list_files_in_dir, LegacyXIP, Identifiers_biblio,
                                          Identifiers_catalog, source_ID, security_tag, ref_fldr_title,
                                          ref_fldr_desc, opex_desc_metadata, file_checksum_dict)
        try:
            opex_temp = open(temp_opex_file, 'w', encoding='utf-8')
            opex_temp.write("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "\n")
            opex_temp.write(xml_package)
            opex_temp.close()
            root_logger.debug("fCreateFolderOpexFragments 6 : file created " + temp_opex_file)
        except:
            pass
            # root_logger.warning("fCreateFolderOpexFragments : opex could not be created " + temp_opex_file)


def fGetDescriptiveMetadata(fp):
    if os.path.exists(fp):
        root_logger.info(fp)
        xmlObject = ET.parse(fp)
        metadata_root = xmlObject.getroot()
        return metadata_root
    else:
        pass


def Delete_metadata(metadata_file):
    try:
        os.remove(metadata_file)
    except:
        pass


def fCreateFileOpexFragments(file, parent, xip_desc, security_tag):
    list_idents = []
    Identifiers_biblio = ""
    pax_type = ""
    file_noext = os.path.splitext(os.path.basename(file))[0]
    root_logger.info("file_noext " + str(file_noext))
    Identifiers_biblio = ""
    list_folders_in_dir = ''
    list_files_in_dir = ''
    file_checksum_dict = {}
    file_checksum_dict[file] = fv6Checksum(os.path.join(parent, file), 'sha1')
    opex_desc_metadata = ''
    LegacyXIP = ''
    Identifiers_catalog = ''
    source_ID = ""
    ref_fldr_title = file_noext
    ref_fldr_desc = xip_desc

    file_xml_package = fCreateOpexFragment(list_folders_in_dir, list_files_in_dir, LegacyXIP,
                                           Identifiers_biblio, Identifiers_catalog, source_ID, security_tag,
                                           ref_fldr_title, ref_fldr_desc,
                                           opex_desc_metadata, file_checksum_dict)

    opex_file_withext = os.path.join(file + ".opex")
    opex_filepath = os.path.join(parent, opex_file_withext)

    if not os.path.exists(opex_filepath):
        try:
            opex_file = open(opex_filepath, 'w', encoding='utf-8')
            opex_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "\n")
            opex_file.write(file_xml_package)
            opex_file.close()
            root_logger.debug("fCreateFileOpexFragments : file created " + opex_filepath)
        except:
            pass
            # root_logger.warning("fCreateFileOpexFragments : opex could not be created " + opex_filepath)


def fCreatePAXFolderOpexFragments(pax_folder, security_tag):
    metadata_list = []
    pax_folder = pax_folder
    Identifiers_biblio = ""
    Identifiers_catalog = ""
    LegacyXIP = ""
    pax_dir = pax_folder
    list_folders_in_dir.clear()
    list_files_in_dir.clear()
    file_checksum_dict.clear()
    LegacyXIP = ""
    Identifiers_catalog = ""

    dc_metadata = os.path.join(pax_folder.split(pax_folder.split(os.sep)[-1])[0],
                               pax_folder.split(os.sep)[-1].replace('.pax', '') + '_dc.xml')
    root_logger.info(dc_metadata)
    mods_metadata = os.path.join(pax_folder.split(pax_folder.split(os.sep)[-1])[0],
                                 pax_folder.split(os.sep)[-1].replace('.pax', '') + '_mods.xml')
    mets_metadata = os.path.join(pax_folder.split(pax_folder.split(os.sep)[-1])[0],
                                 pax_folder.split(os.sep)[-1].replace('.pax', '') + '_METS.xml')
    techmd_metadata = os.path.join(pax_folder.split(pax_folder.split(os.sep)[-1])[0],
                                   pax_folder.split(os.sep)[-1].replace('.pax', '') + '_TECHMD.xml')

    metadata_list.append(fGetDescriptiveMetadata(dc_metadata))
    metadata_list.append(fGetDescriptiveMetadata(mods_metadata))
    metadata_list.append(fGetDescriptiveMetadata(mets_metadata))
    metadata_list.append(fGetDescriptiveMetadata(techmd_metadata))

    ref_fldr_title = pax_folder.split(os.sep)[-1].replace('.pax', '')
    opex_data_folder = ""
    opex_data_file = ""
    opex_file_name = os.path.basename(pax_dir) + ".opex"
    parent_dir = os.sep.join(pax_dir.split(os.sep)[0:len(pax_dir.split(os.sep)) - 1])
    temp_opex_file = os.path.join(parent_dir, opex_file_name)
    if os.path.isdir(pax_dir):
        for dir in os.listdir(pax_dir):
            list_folders_in_dir.append(dir)
            for d in os.listdir(os.path.join(pax_dir, dir)):
                list_folders_in_dir.append(dir + '/' + d)
            for root, dirs, files in os.walk(os.path.join(pax_dir, dir)):
                for file in files:
                    list_files_in_dir.append(dir + '/' + file.split('.')[0] + '/' + file)
                    root_logger.info(list_files_in_dir)
                    try:
                        file_checksum_dict[dir + '/' + file.split('.')[0] + '/' + file] = fv6Checksum(
                            pax_dir + os.sep + dir + os.sep + file.split('.')[0] + os.sep + file, 'sha1')
                    except FileNotFoundError:
                        file_checksum_dict[dir + '/' + file.split('.')[0] + '/' + file] = fv6Checksum(
                            pax_dir + os.sep + dir + os.sep + file.split('.')[0] + '.' + file.split('.')[
                                1] + os.sep + file, 'sha1')
        root_logger.info(file_checksum_dict)

        DC_NSMAP = fGetDescriptiveMetadata(dc_metadata).nsmap

        dcIdentifiers = fGetDescriptiveMetadata(dc_metadata).findall('.//{http://purl.org/dc/elements/1.1/}identifier', DC_NSMAP)
        source_ID = [pitt_id.text for pitt_id in dcIdentifiers if pitt_id.text is not None and pitt_id.text.startswith('pitt')][0]
        DC_title = fGetDescriptiveMetadata(dc_metadata).find('.//{http://purl.org/dc/elements/1.1/}title', DC_NSMAP).text

        ref_fldr_desc = DC_title
        # Descriptive metadata

        if os.path.isfile(dc_metadata):
            fCreateFileOpexFragments(dc_metadata, pax_folder.split(pax_folder.split(os.sep)[-1])[0], DC_title, 'open')
        if os.path.isfile(mods_metadata):
            fCreateFileOpexFragments(mods_metadata, pax_folder.split(pax_folder.split(os.sep)[-1])[0], DC_title, 'open')
        if os.path.isfile(mets_metadata):
            fCreateFileOpexFragments(mets_metadata, pax_folder.split(pax_folder.split(os.sep)[-1])[0], DC_title, 'open')
        if os.path.isfile(techmd_metadata):
            fCreateFileOpexFragments(techmd_metadata, pax_folder.split(pax_folder.split(os.sep)[-1])[0], DC_title,
                                     'open')

        opex_desc_metadata = metadata_list

        xml_package = fCreateOpexFragment(list_folders_in_dir, list_files_in_dir, LegacyXIP,
                                          Identifiers_biblio, Identifiers_catalog, source_ID, security_tag,
                                          ref_fldr_title, ref_fldr_desc,
                                          opex_desc_metadata, file_checksum_dict)
        try:
            opex_temp = open(temp_opex_file, 'w', encoding='utf-8')
            opex_temp.write("<?xml version=\"1.1\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "\n")
            opex_temp.write(xml_package)
            opex_temp.close()
            root_logger.debug("fCreateFolderOpexFragments 6 : file created " + temp_opex_file)
        except:
            pass
            # root_logger.warning("fCreateFolderOpexFragments : opex could not be created " + temp_opex_file)


def fGet_file_no_ext(full_path):
    no_ext = os.path.splitext(full_path)
    file_no_ext = os.path.basename(no_ext[0])
    return file_no_ext


def fGet_filesize(full_path):
    fsize = os.path.getsize(full_path)
    return fsize


def fQuery_container_folder(qcf_target_folder, bucket_prefix, selection_type):
    root_logger.info("fQuery_container_folder")
    global bucket
    packages = ""
    qcf_parent_folder = ""
    nom_container_folder = ""
    container_to_pass_back = ""
    tlf_count = 0
    if selection_type == "All":
        qcf_parent_folder = qcf_target_folder
    elif selection_type == "ind":
        qcf_parent_folder = os.path.dirname(qcf_target_folder)

    for qroot, qd_names, qf_names in os.walk(qcf_target_folder):
        if tlf_count == 0:
            container_to_pass_back = os.path.basename(qroot)
        for qf in qf_names:
            response = False
            if os.path.isfile(os.path.join(qroot, qf)) and not qf.endswith('.gitkeep'):
                qfull_path = os.path.join(qroot, qf)
                root_logger.info("qfull_path " + str(qfull_path))
                f_size = fGet_filesize(qfull_path)
                f_no_ext = fGet_file_no_ext(qfull_path)
                root_logger.info(f_no_ext)
                path_no_ext = bucket_prefix  + qroot.replace(qcf_parent_folder, "").lstrip("\\").replace("\\",
                                                                                                              "/") + '/' + qf  # remove '/' after bucket prefix to use on a Mac
                root_logger.info("path_no_ext " + str(path_no_ext))
                root_logger.info("path_no_ext " + str(path_no_ext))
                packages = qf
                if Cloud_vendor_target == "AWS":
                    response = fUpload_file(qfull_path, f_no_ext, packages, f_size, path_no_ext)
                else:
                    root_logger.error("NO CLOUD VENDOR PROVIDED IN .INI FILE")
                if response == True:
                    # fDelete_Content(qfull_path)
                    pass
                elif response == False:
                    root_logger.info(": fQuery_container_folder :Upload Error ")
        tlf_count += 1
    return container_to_pass_back


def fUpload_file(file_name, f_no_ext, f_name, f_size, object_name):
    root_logger.info("fUpload_file")
    global AWS_Key
    global AWS_Secret
    global bucket
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name
    # Upload the file
    s3_client = boto3.client('s3', aws_access_key_id=AWS_Key, aws_secret_access_key=AWS_Secret)
    try:
        response = s3_client.upload_file(file_name, bucket, object_name, ExtraArgs={
            "Metadata": {"key": f"{f_no_ext}", "name": f"{f_name}", "size": f"{f_size}"}},
                                         Callback=ProgressPercentage(file_name))
    except botocore.exceptions.ClientError as e:
        root_logger.error(e)
        return False
    return True


def fListUploadDirectory():
    global c_f_input
    c_f_list = []
    dict_containerf = {}
    dict_containerf.clear()
    cf_counter = 1
    for root, dirs, files in os.walk(final):
        for file in files:
            if "ds_store" in file.lower():
                os.remove(os.path.join(root, file))
            else:
                pass
    for containerf in os.listdir(final):
        if containerf.lower().startswith('container'):
            dict_containerf[cf_counter] = containerf
            cf_counter += 1
        else:
            pass
    print("****************************************")

    for c_f_key, c_f_val in dict_containerf.items():
        print(str(c_f_key) + "  : " + str(c_f_val))
    print("Enter ALL to upload all packages, enter the number of the package to upload (for multiple containers enter number seperated by a comma ex: 1,2,3), or QUIT: ")
    
    #take the first command line argument
    if isAutomated is True: print("using ", c_f_input, " as input..")
    else: c_f_input = input()

    if c_f_input == "ALL":
        print("send all")
        sel_type = "All"
        returned_target_folder = fQuery_container_folder(os.path.join(final), bucket_prefix, sel_type)
        for c_f_key, c_f_val in dict_containerf.items():
            c_f_list.append(c_f_val)
        # if start_inc_ingest_wf == 1:
        mThread(c_f_list)
    elif c_f_input == "QUIT":
        sys.exit()
    else:
        c_f_input_list = c_f_input.split(',')
        for c_f_input in c_f_input_list:
            c_f_val_from_dict = dict_containerf.get(int(c_f_input), "NA")
            root_logger.info(os.path.join(final, c_f_val_from_dict))
            sel_type = "ind"
            returned_target_folder = fQuery_container_folder(os.path.join(final, c_f_val_from_dict), bucket_prefix,
                                                             sel_type)
            root_logger.info(returned_target_folder)
        #            if c_f_val_from_dict == "NA":
        #                print("You have selected a number that isn't in the list")
        #            else:
        #                if start_inc_ingest_wf == 1:
        for c_f_input in c_f_input_list:
            c_f_val_from_dict = dict_containerf.get(int(c_f_input), "NA")
            fStart_Workflow(c_f_val_from_dict)


def mThread(c_list):
    mthreads = []
    rep_count = 0
    total_rep_count = 0
    task_result = ""
    with ThreadPoolExecutor(max_workers=max_worker_count) as executor:
        for c_next in c_list:
            root_logger.info(c_next)
            mthreads.append(executor.submit(fStart_Workflow, c_next))
            root_logger.info("mthreads " + str(mthreads))
        for task in as_completed(mthreads):
            task_result = task.result()
    return task_result


def fStart_Workflow(fss_container):
    root_logger.info("fStart_Workflow")
    url = "https://" + hostval + "/sdb/rest/workflow/instances"
    querystring = {"WorkflowContextId": " + wfcontextID + "}
    payload1 = "<StartWorkflowRequest xmlns=\"http://workflow.preservica.com\">\r\n\t<WorkflowContextId>"
    payload2 = wfcontextID
    payload3 = "</WorkflowContextId>\r\n\t"
    payload4 = "<Parameter>\r\n\t"
    payload5 = "<Key>OpexContainerDirectory</Key>\r\n\t"
    payload6 = "<Value>" + bucket_prefix + "/" + fss_container + "</Value>\r\n\t"
    payload7 = "</Parameter>\r\n\t"
    payload8 = "</StartWorkflowRequest>"
    payload = payload1 + payload2 + payload3 + payload4 + payload5 + payload6 + payload7 + payload8

    root_logger.info(payload)
    headers = new_token(username, password, basename)
    wf_start_response = requests.request("POST", url, data=payload, headers=headers, params=querystring)
    root_logger.info("fStart_Workflow : Workflow Response : " + wf_start_response.text)
    NSMAP = {"xip_wf": "http://workflow.preservica.com"}

    b_wf_start_response = bytes(wf_start_response.text, 'utf-8')
    parser = lxml.etree.XMLParser(remove_blank_text=True, ns_clean=True)
    wf_tree = lxml.etree.fromstring(b_wf_start_response, parser)
    workflow_id = wf_tree.xpath("//xip_wf:WorkflowInstance/xip_wf:Id", namespaces=NSMAP)
    for wfid in range(len(workflow_id)):
        wf_id = workflow_id[wfid].text
        print("workflow id " + str(wf_id))
        fCheckWorkflowStatus(wf_id)


def fCheckWorkflowStatus(fc_wf_id):
    root_logger.info("fCheckWorkflowStatus")
    r_wf_state = "starting"
    wf_loop_count = 0
    headers = new_token(username, password, basename)
    while True:
        if wf_loop_count > 10:
            print("LOG INTO PRESERVICA AND CHECK THE WORKFLOW STATUS")
            break
        time.sleep(60)
        url = "https://" + hostval + "/sdb/rest/workflow/instances/" + fc_wf_id
        headers = new_token(username, password, basename)
        r_wf_start_response = requests.request("GET", url, headers=headers)
        root_logger.info("fCheckWorkflowStatus : Workflow Response " + r_wf_start_response.text)
        NSMAP = {"xip_wf": "http://workflow.preservica.com"}
        b_r_wf_start_response = bytes(r_wf_start_response.text, 'utf-8')
        parser = lxml.etree.XMLParser(remove_blank_text=True, ns_clean=True)
        r_wf_tree = lxml.etree.fromstring(b_r_wf_start_response, parser)
        r_workflow_state = r_wf_tree.xpath("//xip_wf:WorkflowInstance/xip_wf:State", namespaces=NSMAP)
        for r_wfstate in range(len(r_workflow_state)):
            r_wf_state = r_workflow_state[r_wfstate].text
            print("workflow state " + str(r_wf_state))
        if r_wf_state.lower() != "active":
            print("workflow state " + str(r_wf_state))
            break
        wf_loop_count += 1


# define ini file
config_input = "pitt.ini"
config = configparser.ConfigParser()
config.sections()
config.read(config_input)

container_list = []
c_list_folders_in_dir = []
list_accession_folder = []
list_folders_in_dir = []
list_files_in_dir = []
list_folder_desc = []
folders = []
hash_list = []
hash_type = []
file_list = []
filepath_list = []
file_dict = {}
file_checksum_dict = {}
container_dict = {}
collection_desc = []
number_of_max_workers = 10
threads = []
list_ini = []

bucket_prefix = str(config['VARIABLES']['Bucket_prefix'])
hostval = config['DEFAULT']['Host']
masterDir_path = config['DEFAULT']['MasterDirectory']
source = config['DEFAULT']['Source']
username = config['DEFAULT']['Username']
password = config['DEFAULT']['Password']
basename = hostval
Cloud_vendor_target = str(config['BUCKET']['CV_Target'])
bucket = str(config['BUCKET']['BUCKET'])
AWS_Key = str(config['BUCKET']['KEY'])
AWS_Secret = str(config['BUCKET']['SECRET'])
wfcontextID = str(config['BUCKET']['Workflow_contextID'])
max_worker_count = 5

working_area_dirs = ['Working']

final = Path(masterDir_path) / 'Final'
logs = Path(masterDir_path) / 'Logs'

###Logging
LogFile = os.path.join(logs, "Log_" + str(fTime()) + ".log")
root_logger = logging.getLogger()  # logging object created
root_logger.setLevel(logging.INFO)
handler = logging.FileHandler(LogFile, 'w', 'utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
root_logger.addHandler(handler)
root_logger.info("log file for " + str(os.path.basename(__file__)))

if isAutomated is True:
    print("using ", first_step, " as input..")
else:
    first_step = input(
        'Select the process you would like to run. Enter 1 to Create New Containers or 2 to Upload Previously Created Containers :: ')

if first_step == '1':
    sanitize_working_area(masterDir_path, 'Working')
    os.makedirs(Path(masterDir_path) / 'Working')
    os.makedirs(Path(masterDir_path) / 'Final', exist_ok=True)
    os.makedirs(Path(masterDir_path) / 'Logs', exist_ok=True)
    working = Path(masterDir_path) / 'Working'
    for root, dirs, files in os.walk(source):
        for file in files:
            if file.endswith('.zip'):
                with ZipFile(os.path.join(root, file), 'r') as zObject:
                    zObject.extractall(
                        path=root)
                os.remove(os.path.join(root, file))  # remove zip file

    for root, dirs, files in os.walk(source):
        for file in files:
            if file.startswith('RELS-EXT') and os.path.join(root, file).split(os.sep)[-2] == 'data':
                parent_folders = os.path.join(root, file).replace(str(os.sep) + 'RELS-EXT.rdf', '')
                # print(os.path.join(root, file))

                collection_folder = parent_folders.split(os.sep)
                collection_folder_path = os.sep.join(list(reversed(list(reversed(collection_folder))[2:])))
                xml = ET.parse(os.path.join(root, file))
                metadata_root = xml.getroot()
                nsmap = metadata_root.nsmap
                try:
                    islandora_model = metadata_root.find('.//fedora-model:hasModel', nsmap).attrib[
                        '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource']
                except SyntaxError:
                    islandora_model = metadata_root.find('.//{info:fedora/fedora-system:def/model#}hasModel', nsmap).attrib[
                        '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource']
                if islandora_model == 'info:fedora/islandora:compoundCModel':
                    asset_parent = parent_folders.split(os.sep)[-2]
                    # do something for compound objects
                    for r, ds, fs in os.walk(parent_folders.replace(str(os.sep) + 'data', '')):
                        for f in fs:
                            if f.startswith('MODS') and os.path.join(r, f).split(os.sep)[
                                -2] == 'data' and 'us_ppiu' not in \
                                    root.split(os.sep)[-2].lower():
                                pass
                                mods_fp = os.path.join(r, f)
                                xmlObject = ET.parse(
                                    os.path.join(r,
                                                 f))  # create an xml object that python can parse using lxml libraries
                                root_element = xmlObject.getroot()
                                nsmap = root_element.nsmap
                                # print(ET.tostring(root, pretty_print=True).decode())
                                if root_element.find('.//{http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}identifier',
                                                     nsmap) is not None:  # testing for {http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}Identifier. This will determine the folder heirarchy
                                    relatedID = root_element.find('.//{http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}identifier', nsmap).text
                                    directory_list = [
                                        relatedID + ' ' + note.attrib['type'] + ' ' + note.text.split(' ')[0].rstrip(
                                            '.')
                                        for note in root_element.findall('.//{http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}note[@type]', nsmap) if
                                        note.attrib['type'] == 'series' or note.attrib['type'] == 'subseries' or
                                        note.attrib['type'] == 'otherlevel']
                                    directory_list.append(asset_parent.replace('Bag-', ''))
                                    # print(directory_list)
                                    collection = collection_folder_path.split('Source' + os.sep)[-1].split(os.sep)[0]
                                    for child_dir in os.listdir(parent_folders):
                                        if os.path.isdir(os.path.join(parent_folders, child_dir)):
                                            root_logger.info(child_dir)
                                            asset_folder = child_dir.replace('.', '_') + '.pax'
                                            os.makedirs(
                                                os.path.join(working, collection, os.sep.join(directory_list),
                                                             asset_folder,
                                                             'Representation_Preservation_1',
                                                             child_dir.replace('.', '_')),
                                                exist_ok=True)
                                            for child_f in os.listdir(os.path.join(parent_folders, child_dir)):
                                                if child_f.startswith('OBJ'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection, directory_list,
                                                                             asset_folder,
                                                                             'Representation_Preservation_1',
                                                                             child_dir.replace('.', '_'),
                                                                             child_dir.replace('.', '_') + '.' +
                                                                             child_f.split('.')[-1]))
                                                if child_f.startswith('DC'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             directory_list,
                                                                             child_dir.replace('.', '_') + '_dc.xml'))
                                                if child_f.startswith('MODS'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             directory_list,
                                                                             child_dir.replace('.', '_') + '_mods.xml'))
                                                if child_f.startswith('METS'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             directory_list,
                                                                             child_dir.replace('.', '_') + '_METS.xml'))
                                                if child_f.startswith('TECHMD'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             directory_list,
                                                                             child_dir.replace('.',
                                                                                               '_') + '_TECHMD.xml'))
                                    shutil.copy(mods_fp, os.path.join(working, collection, os.sep.join(directory_list),
                                                                      asset_parent.replace('Bag-', '').replace('.',
                                                                                                               '_') + '_mods' + '.xml'))  # moving folder level metadata to working
                                else:
                                    # figure out what to do if there is no folder heirarchy
                                    collection = r.split('Source' + os.sep)[-1].split(os.sep)[0]
                                    root_logger.info(collection)
                                    for child_dir in os.listdir(parent_folders):
                                        if os.path.isdir(os.path.join(parent_folders, child_dir)):
                                            # print(child_dir)
                                            asset_folder = child_dir.replace('.', '_') + '.pax'
                                            os.makedirs(
                                                os.path.join(working, collection, asset_parent.replace('Bag-', ''),
                                                             asset_folder, 'Representation_Preservation_1',
                                                             child_dir.replace('.', '_')), exist_ok=True)
                                            for child_f in os.listdir(os.path.join(parent_folders, child_dir)):
                                                if child_f.startswith('OBJ'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             asset_parent.replace('Bag-', ''),
                                                                             asset_folder,
                                                                             'Representation_Preservation_1',
                                                                             child_dir.replace('.', '_'),
                                                                             child_dir.replace('.', '_') + '.' +
                                                                             child_f.split('.')[-1]))
                                                if child_f.startswith('DC'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             asset_parent.replace('Bag-', ''),
                                                                             child_dir.replace('.', '_') + '_dc.xml'))
                                                if child_f.startswith('MODS'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             asset_parent.replace('Bag-', ''),
                                                                             child_dir.replace('.', '_') + '_mods.xml'))
                                                if child_f.startswith('METS'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             asset_parent.replace('Bag-', ''),
                                                                             child_dir.replace('.', '_') + '_METS.xml'))
                                                if child_f.startswith('TECHMD'):
                                                    shutil.copy(os.path.join(parent_folders, child_dir, child_f),
                                                                os.path.join(working, collection,
                                                                             asset_parent.replace('Bag-', ''),
                                                                             child_dir.replace('.',
                                                                                               '_') + '_TECHMD.xml'))
                                    shutil.copy(mods_fp,
                                                os.path.join(working, collection, asset_parent.replace('Bag-', ''),
                                                             asset_parent.replace('Bag-', '') + '_mods' + '.xml'))


                else:
                    for r, ds, fs in os.walk(parent_folders.replace(str(os.sep) + 'data', '')):
                        for f in fs:
                            if f.startswith('MODS') and os.path.join(r, f).split(os.sep)[
                                -2] == 'data' and 'us_ppiu' not in \
                                    r.split(os.sep)[-2].lower():
                                mods_fp = os.path.join(r, f)
                                # print(mods_fp)
                                xmlObject = ET.parse(
                                    os.path.join(r,
                                                 f))  # create an xml object that python can parse using lxml libraries
                                root_element = xmlObject.getroot()
                                nsmap = root_element.nsmap
                                if root_element.find('.//{http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}identifier',
                                                     nsmap) is not None:  # testing for {http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}Identifier. This will determine the folder heirarchy
                                    relatedID = root_element.find('.//{http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}identifier', nsmap).text
                                    directory_list = [
                                        relatedID + ' ' + note.attrib['type'] + ' ' + note.text.split(' ')[0].rstrip(
                                            '.')
                                        for note
                                        in root_element.findall('.//{http://www.loc.gov/mods/v3}relatedItem/{http://www.loc.gov/mods/v3}note[@type]', nsmap) if
                                        note.attrib['type'] == 'series' or note.attrib['type'] == 'subseries' or
                                        note.attrib[
                                            'type'] == 'otherlevel']
                                    collection = r.split('Source' + os.sep)[-1].split(os.sep)[0]
                                    asset_folder = r.split('Bag-')[-1].split(os.sep)[0].replace('.', '_') + '.pax'

                                    for top, middle, bottom in os.walk(parent_folders):
                                        for b in bottom:
                                            if b.startswith('OBJ'):
                                                os.makedirs(
                                                    os.path.join(working, collection, os.sep.join(directory_list),
                                                                 asset_folder, 'Representation_Preservation_1',
                                                                 top.split(os.sep)[-1].replace('.', '_').replace(
                                                                     'Bag-', '')), exist_ok=True)
                                                shutil.copy(os.path.join(top, b),
                                                            os.path.join(working, collection,
                                                                         os.sep.join(directory_list),
                                                                         asset_folder, 'Representation_Preservation_1',
                                                                         top.split(os.sep)[-1].replace('.',
                                                                                                       '_').replace(
                                                                             'Bag-', ''),
                                                                         top.split(os.sep)[-1].replace('.',
                                                                                                       '_').replace(
                                                                             'Bag-', '') + '.' + b.split('.')[-1]))

                                    shutil.copy(mods_fp, os.path.join(working, collection, os.sep.join(directory_list),
                                                                      r.split('Bag-')[-1].split(os.sep)[0].replace('.',
                                                                                                                   '_') + '_mods' + '.xml'))
                                    for a in os.listdir(r):
                                        root_logger.info(a)
                                        x = re.findall(r'DC.\w+', os.path.join(r, a))
                                        if x:
                                            shutil.copy(os.path.join(r, a), os.path.join(working, collection,os.sep.join(directory_list),r.split('Bag-')[-1].split(
                                                                                                    os.sep)[0].replace('.',
                                                                                                                       '_') + '_dc' + '.xml'))
                                    for b in os.listdir(r):
                                        x = re.findall(r'METS.\w+', os.path.join(r, b))
                                        if x:
                                            shutil.copy(os.path.join(r, b),
                                                    os.path.join(working, collection, os.sep.join(directory_list),
                                                                 r.split('Bag-')[-1].split(os.sep)[0].replace('.',
                                                                                                              '_') + '_METS' + '.xml'))
                                    for c in os.listdir(r):
                                        x = re.findall(r'TECHMD.\w+', os.path.join(r, c))
                                        if x:
                                            shutil.copy(os.path.join(r, c),
                                                    os.path.join(working, collection, os.sep.join(directory_list),
                                                                 r.split('Bag-')[-1].split(os.sep)[0].replace('.',
                                                                                                              '_') + '_TECHMD' + '.xml'))
                                else:
                                    # figure out what to do if there is no folder heirarchy
                                    collection = r.split('Source' + os.sep)[-1].split(os.sep)[0]
                                    asset_folder = r.split('Bag-')[-1].split(os.sep)[0].replace('.', '_') + '.pax'
                                    for top, middle, bottom in os.walk(parent_folders):
                                        for b in bottom:
                                            if b.startswith('OBJ'):
                                                os.makedirs(os.path.join(working, collection, asset_folder,
                                                                         'Representation_Preservation_1',
                                                                         top.split(os.sep)[-2].replace('.',
                                                                                                       '_').replace(
                                                                             'Bag-', '')), exist_ok=True)
                                                shutil.copy(os.path.join(top, b),
                                                            os.path.join(working, collection, asset_folder,
                                                                         'Representation_Preservation_1',
                                                                         top.split(os.sep)[-2].replace('.',
                                                                                                       '_').replace(
                                                                             'Bag-', ''),
                                                                         top.split(os.sep)[-2].replace('.',
                                                                                                       '_').replace(
                                                                             'Bag-', '') + '.' + b.split('.')[-1]))
                                    shutil.copy(mods_fp, os.path.join(working, collection,
                                                                      r.split('Bag-')[-1].split(os.sep)[0].replace('.',
                                                                                                                   '_') + '_mods' + '.xml'))
                                    for a in os.listdir(r):
                                        root_logger.info(a)
                                        x = re.findall(r'DC.\w+', os.path.join(r, a))
                                        if x:
                                            shutil.copy(os.path.join(r, a), os.path.join(working, collection,
                                                                                                r.split('Bag-')[-1].split(
                                                                                                    os.sep)[0].replace('.',
                                                                                                                       '_') + '_dc' + '.xml'))
                                    for b in os.listdir(r):
                                        x = re.findall(r'METS.\w+', os.path.join(r, b))
                                        if x:
                                            shutil.copy(os.path.join(r, b), os.path.join(working, collection, 
                                                                 r.split('Bag-')[-1].split(os.sep)[0].replace('.',
                                                                                                              '_') + '_METS' + '.xml'))
                                    for c in os.listdir(r):
                                        x = re.findall(r'TECHMD.\w+', os.path.join(r, c))
                                        if x:
                                            shutil.copy(os.path.join(r, c), os.path.join(working, collection, 
                                                                 r.split('Bag-')[-1].split(os.sep)[0].replace('.',
                                                                                                              '_') + '_TECHMD' + '.xml'))
            if file.startswith('DC') and root.split(os.sep)[-1].startswith('collection'):
                os.makedirs(os.path.join(working, root.split(os.sep)[-1]), exist_ok=True)
                shutil.copy(os.path.join(root, file),
                            os.path.join(working, root.split(os.sep)[-1], root.split(os.sep)[-1] + '_' + 'DC.xml'))
            if file.startswith('EAD'):
                os.makedirs(os.path.join(working, root.split(os.sep)[-3]), exist_ok=True)
                shutil.copy(os.path.join(root, file),
                            os.path.join(working, root.split(os.sep)[-3], root.split(os.sep)[-3] + '_' + 'EAD.xml'))
    #
    for root, dirs, files in os.walk(working):
        for dir in dirs:
            if dir.endswith('.pax'):
                pax_dir_fp = os.path.join(root, dir)
                fCreatePAXFolderOpexFragments(pax_dir_fp, security_tag='open')
    #
    for root, dirs, files in os.walk(working):
        #print(root)
        #print(re.split(r'(\/\w+.pax)|(\\pitt\S+.pax)', root)[0])
        folders.append(re.split(r'(\/\w+.pax)|(\/pitt\S+.pax)', root)[0])

    folders_deduped = list(set(folders))

    ####Need to figure out how to write DC metadata and EAD (where applicable to collection level folder
    for folder in folders_deduped:
        root_logger.info(folder)
        if folder.split(os.sep)[-1] != 'Working':
            fCreateFolderOpexFragments(folder, 'open')

    shutil.move(str(working), str(os.path.join(final, "Container_{}".format(str(fTime())))))

    for root, dirs, file in os.walk(final):
        for dir in dirs:
            if 'Container' in dir:
                container_list.append(dir)

    # iterate over container list to create container OPEX
    for c in container_list:
        root_logger.debug('Creating container OPEX for {}'.format(c))
        container_path = os.path.join(final, c)
        list_folders_in_dir.clear()
        list_files_in_dir.clear()
        file_checksum_dict.clear()
        if os.path.isdir(container_path):
            c_opex_data_folder = ""
            c_opex_data_file = ""
            c_opex_file_name = c + ".opex"
            c_temp_opex_file = os.path.join(container_path, c_opex_file_name)
            for c_child in os.listdir(container_path):
                root_logger.info(c_child)
                if os.path.isdir(os.path.join(container_path, c_child)):  # ignore the .opex file
                    list_folders_in_dir.append(c_child)
            # print(c_list_folders_in_dir)
            opex_fixity_type = ""
            opex_fixity_checksum = ""

            source_ID = ""
            LegacyXIP = ""
            Identifiers_biblio = ""
            Identifiers_catalog = ""
            security_tag = ""
            ref_fldr_title = ""
            ref_fldr_desc = ""
            opex_desc_metadata = ""
            c_xml_package = fCreateOpexFragment(list_folders_in_dir, list_files_in_dir, LegacyXIP,
                                                Identifiers_biblio, Identifiers_catalog, source_ID, security_tag,
                                                ref_fldr_title, ref_fldr_desc,
                                                opex_desc_metadata, file_checksum_dict)
            try:
                c_opex_temp = open(c_temp_opex_file, 'w', encoding='utf-8')
                c_opex_temp.write("<?xml version=\"1.1\" encoding=\"UTF-8\" standalone=\"yes\"?>" + "\n")
                c_opex_temp.write(c_xml_package)
                c_opex_temp.close()
                root_logger.info("fCreateContainerFolderOpexFragment : file created " + c_temp_opex_file)
            except:
                pass
                root_logger.warning(
                    "fCreateContainerFolderOpexFragment : opex could not be created " + c_temp_opex_file)

    # send files to S3 bucket
    if isAutomated is True: print("Using ", send_to_s3, " as input")
    else: 
        send_to_s3 = input(
            '\nPAXs created and ready for upload. To send data to s3 bucket and begin Preservica ingest enter 1. To stop the process and review packaged content on local device enter 0: ')

    if send_to_s3 == '1':
        fListUploadDirectory()
else:
    final = Path(masterDir_path) / 'Final'
    logs = Path(masterDir_path) / 'Logs'

    LogFile = os.path.join(logs, "Log_" + str(fTime()) + ".log")
    root_logger = logging.getLogger()  # logging object created
    root_logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LogFile, 'w', 'utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
    root_logger.addHandler(handler)
    root_logger.info("log file for " + str(os.path.basename(__file__)))

    print('uploading containers to s3 bucket')
    fListUploadDirectory()
