#!/usr/bin/env python3
# importing the required modules
from cmath import log
from dataclasses import field
from datetime import datetime, timedelta
from distutils.command.build import build
from importlib.metadata import files
import os
from os import path
import sys
import shutil
import logging
import argparse
import zipfile
import reset_test
from yaml import parse

# Walk through given directory and process the tags found within
def process_tag(dtime, htime, base_path):
    
    # Validate Path
    try:
        if not os.path.exists(base_path):
            raise
    except:
        print("[process_tag] Info: Invalid Path Input. Exiting.")
        return 0
    
    # Define Dictionary containing tag information
    tag = {}

    # Define Dictionary containing number of compressed and deleted files
    results = dict(
            DeletedFiles=0,
            DeletedFolders=0,
            DeletedArchives=0,
            CompressedFolders=0,
            CompressedFiles=0,
            TotalArchives=0
    )

    # Describe what type of clean we are performing. ex. releases or builds
    cln_type = os.path.basename(base_path)

    # Case 1: Process "releases"
    for root, dirs, files in os.walk(base_path):
        
                # Search for directory where walking.yml resides    
        if "walking.yml" in files:
            
            # CASE 1: folder has no tag and is a release
            if "system.tag" not in files and cln_type != "builds":
                # move the walking.yml up one level
                build_path = os.path.abspath(os.path.join(root,os.pardir))
                walking_path = os.path.join(root,'walking.yml')
                shutil.move(walking_path,build_path)
                onlyfiles = [f for f in os.listdir(build_path) if os.path.isfile(os.path.join(build_path,f))]
                onlydirs = [f for f in os.listdir(build_path) if os.path.isdir(os.path.join(build_path,f))]
                create_tag(build_path,"not_ready_to_delete", "This directory had no tag", onlydirs,onlyfiles)

            # CASE 2: folder has no tag and is a generic build folder
            elif "system.tag" not in files:
                create_tag(root,"not_ready_to_delete", "This directory had no tag", dirs,files)
            
            # CASE 3: folder contains a tag
            elif "system.tag" in files:
                tag_path = os.path.join(root,"system.tag")      # path of tag file
                tag = parse_tag(tag_path)  
                results = execute_instruction(tag, results, dtime, htime)

            # CASE 3: Directory has no tag but is younger than (length of time)
            else: 
                pass

    return results

def get_size(base_path):

    size = 0
    for root,dirs,files in os.walk(base_path):
        for f in files:
            fp = os.path.join(root,f)
            size += os.path.getsize(fp)

    size = convert_bytes(size)
    return size

# parse through tag and return the commands and values contained within tag file.
def parse_tag(path):
    
    tag_dict = {}
    # Open log file
    with open(path) as fin:
        # Iterate through, clean and copy items to list
        for line in fin:
            x = line.split('~')
            field = x[0] # instruction or description
            value = x[1][:-1] # value of name

            # Convert string to list for dirs and files 
            if field == 'Folders' or field =='Files':
                li = []
                tag_dict[field] = value[1:-1].split(', ')
                for str in tag_dict[field]:
                    li.append(str[1:-1])
                tag_dict[field] = li 
            elif field == 'CreationDate':
                head, sep, tail = value.partition('.') # change seconds to int
                value = datetime.strptime(head, '20%y-%m-%d %H:%M:%S')
                tag_dict[field] = value
            else:
                tag_dict[field] = value

    return tag_dict

def execute_instruction(tag_dict, results, dtime, htime):

    root = tag_dict.get("Root")
    instruction = tag_dict.get("Instruction")
    reason = tag_dict.get("Reason")
    ctime = tag_dict.get("CreationDate")
    build_name = os.path.basename(tag_dict.get("Root"))
    
    if instruction == "keep":
        pass

    # Older than 6 months and younger than 12 
    elif ctime <= htime and ctime > dtime and instruction != "compressed":
        instruction = "compress"
        reason = "This folder was created between 6 and 12 months ago"
    # Older than 12 months 
    elif ctime < dtime and instruction != "deleted":
        instruction = "delete"
        reason = "This folder was created more than 12 months ago "

    else: 
        instruction = "not_ready_to_delete"
        reason = "This folder was created less than 6 months ago"
        pass

    # Evaluate and execute the instructions
    if instruction == "not_ready_to_delete":
        #print(f'***NOT READY*** \n ROOT: {root} \n REASON: {reason} \n')
        pass

    elif instruction == "compress":
        logging.info(f'***COMPRESSING*** \nBUILD: {build_name} \nREASON: {reason} ')
        zip_path = os.path.join(tag_dict.get("Root"),"archive.zip")
        results = compress_contents(tag_dict, results, reason, zip_path)

    elif instruction == "delete":
        logging.info(f'###DELETING### \nBUILD: {build_name} \nREASON: {reason} ')
        results = delete_contents(tag_dict,results, reason)


    else:
        pass

    return results

def compress_contents(tag, results, reason, zip_filename):
    logging.info("Compressing...")
    dirs = tag.get("Folders")
    files = tag.get("Files")
    zip_file = zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED)

    for dir in dirs:
        dpath = os.path.join(tag.get("Root"), dir)
        for dirpath, dirnames, filenames in os.walk(dpath):
            for filename in filenames:
                zip_file.write(os.path.join(dirpath,filename), os.path.relpath(os.path.join(dirpath,filename), os.path.join(dpath, '..')))
                
    for file in files:
        filepath = os.path.join(tag.get("Root"),file)
        zip_file.write(filepath, os.path.relpath(filepath,os.path.join(filepath, '..')))
    zip_file.close()
    results["TotalArchives"] +=1
    
    logging.info(f"Compressed as {zip_filename}")

    logging.info("Deleting Leftover Folders...")
    #After zip file is created, delete all contents of this folder besides the tag, walking.yml and the archive.
    for dir in tag.get("Folders"):
        results["CompressedFolders"] += 1
        dir_path = os.path.join(tag.get("Root"), dir)
        if os.path.isdir(dir_path):
            shutil.rmtree(dir_path)
            logging.info(f"    -> {dir}")
        else:
            logging.info(f"Folder does not exist -> {dir}")
    logging.info("Deleting Leftover Files...")
    # iterate through list of files and delete all but the walking.yml
    for file in tag.get("Files"):
        results["CompressedFiles"] += 1
        file_path = os.path.join(tag.get("Root"), file)
        if os.path.isfile(file_path) and file != "walking.yml":
            os.remove(file_path)
            logging.info(f"    -> {file}")
        elif file == "walking.yml":
            logging.info(f"    -> {file} preserved, continuing...")
        else:
            logging.info(f"WARNING: file -> {file} does not exist")
    logging.info("\nFinished Deleting")

    # Update tag 
    logging.info("Updating tag...")
    tag["Instruction"] = "compressed"
    tag["Reason"] = reason
    edit_tag(tag)
    logging.info("*****DONE******\n")

    return results

# given a tag, delete the contents that are local to that tag whilst keeping archive of what is deleted.
def delete_contents(tag, results, reason):

    # Check if this build has already been archived and if so, delete the zip file
    if tag.get("Instruction") == "compressed":
        path_to_archive = os.path.join(tag.get("Root"),"archive.zip")
        file = os.path.basename(path_to_archive)
        
        logging.info(f"Deleting Archive...")
        logging.info(f"    -> {file}")
        os.remove(path_to_archive)
        logging.info("Archive deleted")
        results["DeletedArchives"] += 1
 
    else:
        # iterate through list of files and delete all but the walking.yml
        logging.info("Deleting Files...")
        for file in tag.get("Files"):
            file_path = os.path.join(tag.get("Root"), file)
            if os.path.isfile(file_path) and file != "walking.yml":
                os.remove(file_path)
                logging.info(f"    -> {file}")
                results["DeletedFiles"] += 1
            elif file == "walking.yml":
                logging.info(f"    -> {file} preserved, continuing...")
            else:
                logging.info(f"WARNING: file -> {file} does not exist")
    
        logging.info("Files cleaned\n")
        logging.info("Deleting Folders...")
        # iterate through list of folders and delete all 
        for dir in tag.get("Folders"):
            dir_path = os.path.join(tag.get("Root"), dir)
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
                logging.info(f"    -> {dir}")
                results["DeletedFolders"] +=1
            else:
                logging.info("Folder does not exist")
        logging.info("Folders cleaned")
        

    # Update tag file
    logging.info("Updating Tag...")
    tag["Instruction"] =  "deleted"
    tag["Reason"] = reason
    edit_tag(tag)
    logging.info("####DONE####\n")
    
    return results

# Given a tag dict, rewrite the tag file to update its values 
def edit_tag(tag_dict): 
    tag_path = os.path.join(tag_dict.get("Root"),"system.tag") 
    tag_str = ''
    os.remove(tag_path)

    # Create new tag
    with open(tag_path, 'w') as fout:
        tag_str += "Root~" + tag_dict.get("Root")+ "\n"
        tag_str += "CreationTime~" + tag_dict.get("CreationTime") +"\n"
        tag_str += "CreationDate~" + str(tag_dict.get("CreationDate"))+ "\n"
        tag_str += "Instruction~" + tag_dict.get("Instruction")+ "\n"
        tag_str += "Reason~" + tag_dict.get("Reason")+ "\n"
        tag_str += "Folders~" + str(tag_dict.get("Folders"))+ "\n"
        tag_str += "Files~" + str(tag_dict.get("Files"))+"\n"
        tag_str += "Notes~" + tag_dict.get("Notes") + "\n"
        fout.write(tag_str)

    return 0

# given a path and an instruction generate a tag to place in path
def create_tag(root_path, instruction, reason, dirs, files):
        build_name = os.path.basename(root_path)
        logging.info(f"CREATE TAG -> BUILD NAME: {build_name} | INSTRUCTION: {instruction} | REASON: {reason}")
        tag_path = os.path.join(root_path,"system.tag")
        tag_str = ""
        ctime = os.path.getctime(root_path)
        dt_c = datetime.fromtimestamp(ctime)

        if instruction == "not_ready_to_delete":
            with open(tag_path,'w') as fout:

                tag_str += "Root~" + root_path + "\n"
                tag_str += f"CreationTime~{ctime}\n"
                tag_str += f"CreationDate~{dt_c}\n"
                tag_str += "Instruction~" + instruction + "\n"
                tag_str += "Reason~" + reason + "\n"
                tag_str += f"Folders~{dirs}\n"
                tag_str += f"Files~{files}\n"
                tag_str += "Notes~\n"
                fout.write(tag_str)
            
            #logging.info(f"{instruction} -> Generated in {root_path} ")


        return 0 

def convert_bytes(bytes_number):
    tags = [ "B", "KB", "MB", "GB", "TB" ]
 
    i = 0
    double_bytes = bytes_number
 
    while (i < len(tags) and  bytes_number >= 1024):
            double_bytes = bytes_number / 1024.0
            i = i + 1
            bytes_number = bytes_number / 1024
 
    return str(round(double_bytes, 2)) + " " + tags[i]

def get_args():
    parser = argparse.ArgumentParser(description="Search through given directory and execute instructions given by a tag file")
    parser.add_argument("-t", "--time",         help="A length of time in months, required", required=True)
    parser.add_argument("-p", "--base_path",    help="Path to the directory that requires cleaning",required=True)
    return parser.parse_args()
 
def setup_log(base_path):

    date = datetime.now().strftime("%m_%d_%Y")
    
    # Initialize the log
    log_file = f'{date}.log'
    log_format = '%(message)s'  # log_format = '%(asctime)s %(levelname)s: %(message)s'
    log_level = 'INFO'          # Possible levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    log_fh = logging.FileHandler(log_file)
    log_sh = logging.StreamHandler(sys.stdout)
    logging.basicConfig(format=log_format, level=log_level, handlers=[log_sh, log_fh])     # with handlers
    #logging.basicConfig(filename=log_file, filemode='w',format=log_format, level=log_level) # without handlers (use for write)

    logging.info(f'DATE: {date}')
    # specify the path to root folder
    logging.info(f"ROOT PATH: {base_path}\n")
    logging.info("-----------------------------------------------------")
    
    return 0

if __name__ == '__main__':

    args = get_args()
    dtime = datetime.now() - timedelta(days= int(args.time))        # ex. 2022-08-31 12:41:35.987017
    htime = datetime.now() - timedelta(days= int(args.time)/2)

    # Calculate the original size of folder
    orignal_size = get_size(args.base_path)

    # Create a new log file 
    setup_log(args.base_path)

    # Process the tags and save the results
    results = process_tag(dtime,htime,args.base_path)
    
    # Calulate the leftover size
    final_size = get_size(args.base_path)

    # # Log Summary
    logging.info('---------------------------------\n')
    
    logging.info(f'Deleted Files: {results["DeletedFiles"]}')
    logging.info(f'Deleted Folders: {results["DeletedFolders"]}')
    logging.info(f'Deleted Archives: {results["DeletedArchives"]}\n')

    logging.info(f'Compressed Files: {results["CompressedFiles"]}')
    logging.info(f'Compressed Folders: {results["CompressedFolders"]}')
    logging.info(f'Total Archives Created: {results["TotalArchives"]}\n')
    logging.info(f'Original Size: {orignal_size}\nFinal Size: {final_size}')
    logging.info('\n-----------------------------------------------------\n')


