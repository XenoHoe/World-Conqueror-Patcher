import argparse
import traceback

import shutil
import os
import glob

from encrypt_decryptor import encrypt_file_aes_cbc as encrypt_file
from encrypt_decryptor import decrypt_file_aes_cbc as decrypt_file
from encrypt_decryptor import KEY
from encrypt_decryptor import IV

from config_manager import load_config
from config_manager import update_config

#Extraction Logic:
#all items in the data/ folder:extracted and decrypted
#all pngs with corresponding .xml files will be extracted
#pngs will be disected based on the xml files and stored in corresponding folders

#Patch logic:
#Since all settings files are just a [{},{}...], they will be merged based on ID
#all items in the data/ folder will be decrypted, merged, and re-encrypted.
#pngs in the original file will be dissected based on xmls, merged with the ones in the working directory, and re-assembled

class KeyValueAction(argparse.Action):#This function is AI generated
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

    shutil.rmtree(dest_dir)

    os.makedirs(dest_dir, exist_ok=True)

    #data files
    for pattern in ['*.json','*.xml']:
        file_pattern = os.path.join(game_dir + '/data/',pattern)
        dump_files(file_pattern,dest_dir + '/data/',True)

    #loc files
    localization_pattern = os.path.join(game_dir,'*.ini')
    dump_files(localization_pattern,dest_dir,False)

    return

def main():
    parser = argparse.ArgumentParser(description='Main script that handles patching of files.')

    action_to_run = parser.add_mutually_exclusive_group()

    action_to_run.add_argument('-c','--config', 
                       nargs=2,  # Expect exactly 2 arguments
                       metavar=('KEY', 'VALUE'),  # Help text for the two arguments
                       action=KeyValueAction,
                       help='Configure key-value pair (e.g., --config mod_directory ./my_mod )')
    action_to_run.add_argument('-d','--dump',action='store_true',help = 'Dump supported moddable files in the game directory to ./dump.')
    action_to_run.add_argument('-p','--patch',action='store_true',help = 'Patches files in the working directory into the game directory.')
    
    args = parser.parse_args()

    config  = load_config()

    if args.config:
        update_config_items(args.config)

    if args.dump:
        if config.get('mode') == "macOS":
            dump_game_files(config.get('game_path'))
    
    return

if __name__ == '__main__':
    main()