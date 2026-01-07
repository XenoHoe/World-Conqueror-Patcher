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
        dest_file = shutil.copy(source_path, target_dir)
    except Exception as e:
        print(e)
        print(traceback.format_exc())

    if decrypt:
        decrypt_file(dest_file,KEY,IV)

    return

def dump_files(pattern,target_dir,decrypt = False):
    os.makedirs(target_dir, exist_ok=True)
    files = glob.glob(pattern)
    for file_path in files:
        if os.path.isfile(file_path):
            dump_file(file_path,target_dir,decrypt)
            print(f"Dumped: {os.path.basename(file_path)}")

def dump_game_files(game_dir,dest_dir = './dump'):

    shutil.rmtree(dest_dir)#Clean dump

    os.makedirs(dest_dir, exist_ok=True)

    #data files
    for pattern in ['*.json','*.xml']:
        file_pattern = os.path.join(game_dir + 'data/',pattern)
        dump_files(file_pattern,dest_dir + '/data/',True)

    #loc files
    localization_pattern = os.path.join(game_dir,'*.ini')
    dump_files(localization_pattern,dest_dir,False)

    return

def patch_game_files(mod_dir,game_dir):

    restore_from_backups(game_dir)

    #Make temporary directory
    os.makedirs('temp',exist_ok=True)

    #data
    mod_data_dir = mod_dir + 'data/'

    if os.path.exists(mod_data_dir):
        datafiles = os.listdir(mod_data_dir)
        for file_path in datafiles:

            full_path = mod_data_dir + file_path
            original_file_path = game_dir + 'data/' + file_path

            if os.path.exists(original_file_path):
                backup_file(original_file_path)
                merge_data_file(original_file_path,full_path,True)
            else:
                shutil.copy(full_path,original_file_path)
                #merge_data_file(original_file_path,full_path,True)
    
    loc_pattern = os.path.join(mod_dir,'*.ini')
    loc_files = glob.glob(loc_pattern)
    for file_path in loc_files:
        original_file_path = game_dir + os.path.basename(file_path)
        if os.path.exists(original_file_path):
            backup_file(original_file_path)
            merge_data_file(original_file_path,file_path,False)
        else:
            shutil.copy(file_path,original_file_path)
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
                       help='Configure key-value pair (e.g., --config mod_directory mods/my_mod/ )')
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
        if not game_dir.endswith("/"):
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
    
    elif args.restore:
        if config.get('mode') == "macOS":
            restore_from_backups(game_dir)
    
    elif args.patch:
        if config.get('mode') == "macOS":
            patch_game_files(mod_dir,game_dir)

    
    os.makedirs('mods',exist_ok=True)
    return

if __name__ == '__main__':
    main()