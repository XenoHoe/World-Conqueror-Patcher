import argparse
import traceback

import shutil
import os
import glob

import json

from encrypt_decryptor import encrypt_file_aes_cbc as encrypt_file
from encrypt_decryptor import decrypt_file_aes_cbc as decrypt_file

from config_manager import load_config
from config_manager import update_config

from atlas_manager import process_atlas_element_tree as read_atlas_manifest
from atlas_manager import create_atlas_from_folder

from apk_manager import APKManager

KEY = None
IV = None

#Extraction Logic:
#all items in the data/ folder:extracted and decrypted
#all pngs with corresponding .xml files will be extracted
#pngs will be disected based on the xml files and stored in corresponding folders

#Patch logic:
#Since all settings files are just a [{},{}...], they will be merged based on ID
#all items in the data/ folder will be decrypted, merged, and re-encrypted.
#pngs in the original file will be dissected based on xmls, merged with the ones in the working directory, and re-assembled
#ini files will just be appended, since later keys have priority

class KeyValueAction(argparse.Action):#This class is AI generated
    """Custom action to handle --config key value pairs."""
    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) != 2:
            parser.error(f"{option_string} requires exactly 2 arguments (key and value)")
        
        # Initialize the config dictionary if it doesn't exist
        if not hasattr(namespace, 'config') or namespace.config is None:
            setattr(namespace, 'config', {})
        
        # Add the key-value pair to the config dictionary
        key, value = values
        namespace.config[key] = value


def update_config_items(items):
    config = load_config()
    for key,value in items.items():
        config[key] = value
    update_config(config)

def dump_file(source_path,target_dir = './dump',decrypt = False):
    try:
        os.makedirs(target_dir, exist_ok=True)
        dest_file = shutil.copy(source_path, target_dir)
    except Exception as e:
        print(e)
        print(traceback.format_exc())

    if decrypt:
        decrypt_file(dest_file,KEY,IV)

    return

def dump_files(pattern,target_dir,decrypt = False,preserve_relative_path = False,game_dir = '/'):
    os.makedirs(target_dir, exist_ok=True)
    files = glob.glob(pattern)
    for file_path in files:
        if os.path.isfile(file_path):
            if preserve_relative_path:
                relative_dir = os.path.relpath(os.path.dirname(file_path), game_dir)
                dump_file(file_path,os.path.join(target_dir,relative_dir),decrypt)
                print(f"Dumped: {os.path.basename(file_path)}")
            else:
                dump_file(file_path,target_dir,decrypt)
                print(f"Dumped: {os.path.basename(file_path)}")

def dump_atlas(source_path,game_dir,target_dir = './dump'):
    try:
        return read_atlas_manifest(source_path,game_dir,target_dir)#This function preserves relative paths
    except Exception as e:
        print(e)
        print(traceback.format_exc())


def dump_atlases(pattern,target_dir,game_dir = '/'):
    os.makedirs(target_dir, exist_ok=True)
    files = glob.glob(pattern)
    for file_path in files:
        if os.path.isfile(file_path):
            print(f"Dumped: {os.path.basename(file_path)}")
            dump_atlas(file_path,game_dir,target_dir)
    return

def dump_game_files(game_dir,dest_dir = './dump'):

    shutil.rmtree(dest_dir)#Clean dump

    os.makedirs(dest_dir, exist_ok=True)

    #data files
    for pattern in ['*.json','*.xml']:
        file_pattern = os.path.join(game_dir,'data',pattern)
        dump_files(file_pattern,os.path.join(dest_dir,'data'),decrypt=True)

    #loc files
    localization_pattern = os.path.join(game_dir,'*.ini')
    dump_files(localization_pattern,dest_dir,decrypt=False)

    #image files
    for pattern in ['image/**.webp','image/**/*.webp']:
        image_pattern = os.path.join(game_dir,pattern)
        dump_files(image_pattern,dest_dir,decrypt=False,preserve_relative_path=True,game_dir=game_dir)
    
    #image atlases
    for pattern in ['*.xml','**/*.xml']:
        xml_pattern = os.path.join(game_dir,pattern)
        dump_atlases(xml_pattern,dest_dir,game_dir)
    
    return

def dump_apk_files(apk_path, dest_dir='./dump'):    
    apk = APKManager(apk_path)
    extracted_dir = apk.extract()
    
    #What we can modify is under the assets folder
    assets_dir = os.path.join(extracted_dir, "assets")
    
    if os.path.exists(assets_dir):
        #Everything else is the same
        dump_game_files(assets_dir, dest_dir)
    
    apk.cleanup()

def patch_apk_files(mod_dir, apk_path, output_apk=None):
    apk = APKManager(apk_path)
    extracted_dir = apk.extract()
    
    #Modifying assets
    assets_dir = os.path.join(extracted_dir, "assets")
    if os.path.exists(assets_dir):
        patch_game_files(mod_dir, assets_dir)
        
    #Repacking
    patched_apk = apk.repack(output_apk)
    
    #Signing
    config = load_config()
    if config.get('apk_signing_enabled', False):
        apk.sign_apk(
            patched_apk,
            config.get('apk_keystore'),
            config.get('apk_keystore_pass'),
            config.get('apk_key_alias')
        )
    
    apk.cleanup()
    return patched_apk


def patch_game_files(mod_dir,game_dir):
    is_apk_mode = load_config().get("mode") == "apk"

    restore_from_backups(game_dir)

    #Make temporary directory
    os.makedirs('temp',exist_ok=True)

    #Patching data files
    mod_data_dir = os.path.join(mod_dir,'data')
    mod_image_dir = os.path.join(mod_dir,'image')

    if os.path.exists(mod_data_dir):
        datafiles = os.listdir(mod_data_dir)
        for file_path in datafiles:

            full_path = os.path.join(mod_data_dir,file_path)
            original_file_path = os.path.join(game_dir,'data',file_path)

            if os.path.exists(original_file_path):
                if not is_apk_mode:
                    backup_file(original_file_path)
                merge_data_file(original_file_path,full_path,True)
            else:
                shutil.copy(full_path,original_file_path)
                print("Copied " + original_file_path + ".")
                #merge_data_file(original_file_path,full_path,True)
    
    #Patching localization files
    loc_pattern = os.path.join(mod_dir,'*.ini')
    loc_files = glob.glob(loc_pattern)
    for file_path in loc_files:
        original_file_path = os.path.join(game_dir,os.path.basename(file_path))
        if os.path.exists(original_file_path):
            if not is_apk_mode:
                backup_file(original_file_path)
            merge_data_file(original_file_path,file_path,False)
        else:
            shutil.copy(file_path,original_file_path)
            print("Merged " + original_file_path + ".")
    
    #Patching image files
    if os.path.exists(mod_image_dir):
        for pattern in ['image/**.webp','image/**/*.webp']:
            image_pattern = os.path.join(mod_dir,pattern)
            image_files = glob.glob(image_pattern)
            for file_path in image_files:
                relative_path = os.path.relpath(file_path,mod_dir)
                original_file_path = os.path.join(game_dir,relative_path)
                if os.path.exists(original_file_path) and not is_apk_mode:
                    backup_file(original_file_path)
                shutil.copy(file_path,original_file_path)
                print("Copied " + original_file_path + ".")
    
    #Patching atlases
    for pattern in ['*.png','**/*.png']:
        atlas_pattern = os.path.join(mod_dir,pattern)
        atlas_paths = glob.glob(atlas_pattern)
        for path in atlas_paths:
            if not os.path.isdir(path):#check if is path is valid atlas folder.
                continue
            
            temp_folder = "./temp"

            #Get modified images
            image_pattern = os.path.join(path,'*.png')
            image_paths = glob.glob(image_pattern)
            if len(image_paths) == 0:
                continue
                
            #Get original locations
            relative_path = os.path.relpath(path,mod_dir)
            #original_atlas_image_path = os.path.join(game_dir,relative_path)
            original_atlas_manifest_path = os.path.join(game_dir,relative_path).replace('.png','.xml')

            #First, dump original file to temp directory
            original_atlas_image_path = dump_atlas(original_atlas_manifest_path,game_dir,temp_folder)
            temp_working_dir = os.path.join(temp_folder,os.path.basename(original_atlas_image_path))
            
            #Replace and add
            for image_path in image_paths:
                shutil.copy2(image_path,temp_working_dir)
            
            #Backup original locations
            if not is_apk_mode:
                if os.path.exists(original_atlas_image_path) and os.path.isfile(original_atlas_image_path):
                    backup_file(original_atlas_image_path)
                if os.path.exists(original_atlas_manifest_path) and os.path.isfile(original_atlas_manifest_path):
                    backup_file(original_atlas_manifest_path)

            create_atlas_from_folder(temp_working_dir,os.path.dirname(original_atlas_image_path))
            
            #Remove temp directory
            shutil.rmtree(temp_working_dir)

            print("Modified atlas " + original_atlas_image_path)

    return

def merge_data_file(original_path,modded_path,decrypt = False):
    if original_path.endswith(".json"):

        if decrypt:
            decrypt_file(original_path,KEY,IV)

        with open(original_path,'r') as f:
            original_content = f.read()
            f.close()

        original_content_json = json.loads(original_content)

        with open(modded_path,'r') as f:
            modded_content = f.read()
            f.close()

        modded_content_json = json.loads(modded_content)

        final_content = json.dumps(merge_settings(original_content_json,modded_content_json),indent=None,separators=(',',':'),ensure_ascii=False)\
            .replace('},{', '},\n{').replace('}, {', '},\n{')\
            .replace('[{', '[\n{').replace('}]', '}\n]')

        with open(original_path,'w') as f:
            f.write(final_content)

        if decrypt:
            encrypt_file(original_path,KEY,IV)

    elif original_path.endswith(".xml"): #Not sure how to handle the,, replace
        shutil.copy(modded_path,original_path)
        if decrypt:
            encrypt_file(original_path,KEY,IV)

    elif original_path.endswith(".ini"): #Localization files
        with open(original_path,'r') as f:
            original_content = f.read()
            f.close()
        with open(modded_path,'r') as f:
            modded_content = f.read()
            f.close()
        final_content = original_content + '\n' + modded_content

        with open(original_path,'w') as f:
            f.write(final_content)
        
    else:
        pass
    
    print("merged " + os.path.basename(original_path) + ".")

def merge_atlas_file():
    return

def merge_settings(list1,list2):
    new_list = list1

    for item in list2:
        itemID = item.get("Id",None)

        if not itemID:#Skip if no ID, since that's non standard
            print("Warning: a modded settings Item has no Id. It will be skipped.")
            continue
        
        #If ID mathces, replace original entry
        replaced_flag = False
        for i in range(len(list1)):
            if list1[i].get("Id",None) == itemID:
                list1[i] = item
                replaced_flag = True
                break
        
        #Else, it is a new entry
        if not replaced_flag:
            list1.append(item)

    return new_list

def backup_file(file_path):#Takes path of any file
    backup_path = file_path + ".backup"
    if os.path.exists(backup_path):
        return #Skip if already present
    shutil.copy2(file_path, backup_path)

def restore_backup_file(file_path):#Takes path of .backup file
    original_path = file_path.removesuffix(".backup")
    shutil.copy2(file_path,original_path)

def restore_from_backups(game_dir):
    count = 0
    print(game_dir)
    files = glob.glob(game_dir + "**/*.backup",recursive=True)
    for file_path in files:
        restore_backup_file(file_path)
        count += 1

    print("Restored " + str(count) + " files.")


def main():
    global KEY,IV
    parser = argparse.ArgumentParser(description='Main script that handles patching of files.')

    action_to_run = parser.add_mutually_exclusive_group()

    action_to_run.add_argument('-c','--config', 
                       nargs=2,  # Expect exactly 2 arguments
                       metavar=('KEY', 'VALUE'),  # Help text for the two arguments
                       action=KeyValueAction,
                       help='Configure key-value pair (e.g., --config mod_directory mods/my_mod/ ). Can also be done by modifying config.yaml.')
    action_to_run.add_argument('-d','--dump',action='store_true',help = 'Dump supported moddable files in the game directory to dump/ ')
    action_to_run.add_argument('-p','--patch',action='store_true',help = 'Patches files in the configured mod directory into the game directory')
    action_to_run.add_argument('-r','--restore',action='store_true',help = 'Restore game to original state from backups made by this program')

    args = parser.parse_args()

    config  = load_config()

    if args.config:
        update_config_items(args.config)
    
    game_dir = config.get("game_path")
    mod_dir = config.get("mod_directory")

    KEY = config.get('asset_key').encode() if config.get('asset_key') else None
    IV = config.get('asset_iv').encode() if config.get('asset_iv') else None


    if game_dir:
        if not game_dir.endswith("/") and not config.get('mode') == "apk":
            game_dir = game_dir + "/"
    else:
        print("Game directory not configured. Please configure using main.py -c game_path /path/to/game/root/directory")
        exit()

    if mod_dir:
        if not mod_dir.endswith("/"):
            mod_dir = mod_dir + "/"

    if args.dump:
        if config.get('mode') == "macOS":
            dump_game_files(game_dir)
        elif config.get('mode') == "apk":
            dump_apk_files(game_dir)
        else:
            print("No valid mode (macOS|apk) selected. Nothing will be done.")
    
    elif args.restore:
        if config.get('mode') == "macOS":
            restore_from_backups(game_dir)
        elif config.get('mode') == "apk":
            print("Restoring APK files not supported. Use the original APK instead.")
        else:
            print("No valid mode (macOS|apk) selected. Nothing will be done.")

    elif args.patch:
        if config.get('mode') == "macOS":
            patch_game_files(mod_dir,game_dir)
        elif config.get('mode') == "apk":
            patch_apk_files(mod_dir,game_dir)
        else:
            print("No valid mode (macOS|apk) selected. Nothing will be done.")

    
    os.makedirs('mods',exist_ok=True)
    return

if __name__ == '__main__':
    main()