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

# Extraction Logic:
# all items in the data/ folder: extracted and decrypted
# all pngs with corresponding .xml files will be extracted
# pngs will be dissected based on the xml files and stored in corresponding folders

# Patch logic:
# Since all settings files are just a [{},{}...], they will be merged based on ID
# all items in the data/ folder will be decrypted, merged, and re-encrypted.
# pngs in the original file will be dissected based on xmls, merged with the
# ones in the working directory, and re-assembled
# ini files will just be appended, since later keys have priority


class KeyValueAction(argparse.Action):
    """Custom action to handle --config key value pairs."""
    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) != 2:
            parser.error(f"{option_string} requires exactly 2 arguments (key and value)")
        if not hasattr(namespace, 'config') or namespace.config is None:
            setattr(namespace, 'config', {})
        key, value = values
        namespace.config[key] = value


def update_config_items(items):
    config = load_config()
    for key, value in items.items():
        config[key] = value
    update_config(config)


def dump_file(source_path, target_dir='./dump', decrypt=False):
    try:
        os.makedirs(target_dir, exist_ok=True)
        dest_file = shutil.copy(source_path, target_dir)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    if decrypt:
        decrypt_file(dest_file, KEY, IV)


def dump_files(pattern, target_dir, decrypt=False, preserve_relative_path=False, game_dir='/'):
    os.makedirs(target_dir, exist_ok=True)
    files = glob.glob(pattern)
    for file_path in files:
        if os.path.isfile(file_path):
            if preserve_relative_path:
                relative_dir = os.path.relpath(os.path.dirname(file_path), game_dir)
                dump_file(file_path, os.path.join(target_dir, relative_dir), decrypt)
                print(f"Dumped: {os.path.basename(file_path)}")
            else:
                dump_file(file_path, target_dir, decrypt)
                print(f"Dumped: {os.path.basename(file_path)}")


def dump_atlas(source_path, game_dir, target_dir='./dump'):
    try:
        # Returns (image_path, original_format, output_folder) on success
        return read_atlas_manifest(source_path, game_dir, target_dir)
    except Exception as e:
        print(e)
        print(traceback.format_exc())


def dump_atlases(pattern, target_dir, game_dir='/'):
    os.makedirs(target_dir, exist_ok=True)
    files = glob.glob(pattern)
    for file_path in files:
        if os.path.isfile(file_path):
            print(f"Dumped: {os.path.basename(file_path)}")
            dump_atlas(file_path, game_dir, target_dir)


def dump_game_files(game_dir, dest_dir='dump'):
    shutil.rmtree(dest_dir)  # Clean dump
    os.makedirs(dest_dir, exist_ok=True)

    # data files
    for pattern in ['*.json', '*.xml']:
        file_pattern = os.path.join(game_dir, 'data', pattern)
        dump_files(file_pattern, os.path.join(dest_dir, 'data'), decrypt=True)

    # loc files
    localization_pattern = os.path.join(game_dir, '*.ini')
    dump_files(localization_pattern, dest_dir, decrypt=False)

    # battle files
    battle_pattern = os.path.join(game_dir, 'stage', '*.btl')
    dump_files(battle_pattern, os.path.join(dest_dir, 'stage'), decrypt=False)

    # image files
    for pattern in ['image/**.webp', 'image/**/*.webp']:
        image_pattern = os.path.join(game_dir, pattern)
        dump_files(image_pattern, dest_dir, decrypt=False, preserve_relative_path=True, game_dir=game_dir)

    # image atlases — only parse XML files that are adjacent to a PNG/WebP image
    for pattern in ['*.xml', '**/*.xml']:
        xml_pattern = os.path.join(game_dir, pattern)
        dump_atlases(xml_pattern, dest_dir, game_dir)

    return


def dump_apk_files(apk_path, dest_dir='dump'):
    os.makedirs(dest_dir, exist_ok=True)
    apk = APKManager(apk_path)
    extracted_dir = apk.extract()
    assets_dir = os.path.join(extracted_dir, "assets")
    if os.path.exists(assets_dir):
        dump_game_files(assets_dir, dest_dir)
    apk.cleanup()


def detect_atlas_format(manifest_path, game_dir):
    """
    Determine the actual on-disk format (PNG or WEBP) of an atlas in the
    target game directory by looking for the image file next to the XML manifest.
    This is used during patching so the output matches whatever the target
    platform ships, regardless of where the mod came from.
    """
    directory = os.path.dirname(manifest_path)
    # The XML has no root tag — read just the first line for the Texture name
    with open(manifest_path, 'r') as f:
        first_line = f.readline().strip()
    if 'name="' in first_line:
        name_attr = first_line.split('name="')[1].split('"')[0]
        png_path = os.path.join(directory, name_attr)
        if os.path.exists(png_path) and os.path.isfile(png_path):
            return "PNG"
        webp_path = png_path.replace('.png', '.webp')
        if os.path.exists(webp_path) and os.path.isfile(webp_path):
            return "WEBP"
    # Fallback: check both common names
    base = os.path.splitext(os.path.basename(manifest_path))[0]
    if os.path.exists(os.path.join(directory, base + '.png')):
        return "PNG"
    if os.path.exists(os.path.join(directory, base + '.webp')):
        return "WEBP"
    print(f"Warning: could not detect atlas format from {manifest_path}, defaulting to PNG.")
    return "PNG"


def patch_apk_files(mod_dir, apk_path, output_apk=None):
    apk = APKManager(apk_path)
    extracted_dir = apk.extract()
    assets_dir = os.path.join(extracted_dir, "assets")
    if os.path.exists(assets_dir):
        patch_game_files(mod_dir, assets_dir)

    patched_apk = apk.repack(output_apk)
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


def patch_game_files(mod_dir, game_dir):
    is_apk_mode = load_config().get("mode") == "apk"
    restore_from_backups(game_dir)
    os.makedirs('temp', exist_ok=True)

    mod_data_dir = os.path.join(mod_dir, 'data')
    mod_image_dir = os.path.join(mod_dir, 'image')
    mod_battle_dir = os.path.join(mod_dir, 'stage')

    # ---- Data files ----
    if os.path.exists(mod_data_dir):
        for file_name in os.listdir(mod_data_dir):
            full_path = os.path.join(mod_data_dir, file_name)
            original_file_path = os.path.join(game_dir, 'data', file_name)
            if os.path.exists(original_file_path):
                if not is_apk_mode:
                    backup_file(original_file_path)
                merge_data_file(original_file_path, full_path, True)
            else:
                shutil.copy(full_path, original_file_path)
                print("Copied " + original_file_path + ".")

    # ---- Localization files ----
    loc_pattern = os.path.join(mod_dir, '*.ini')
    for file_path in glob.glob(loc_pattern):
        original_file_path = os.path.join(game_dir, os.path.basename(file_path))
        if os.path.exists(original_file_path):
            if not is_apk_mode:
                backup_file(original_file_path)
            merge_data_file(original_file_path, file_path, False)
        else:
            shutil.copy(file_path, original_file_path)
            print("Merged " + original_file_path + ".")

    # ---- BTL battle files ----
    if os.path.exists(mod_battle_dir):
        for btl_path in glob.glob(os.path.join(mod_dir, 'stage/**.btl')):
            relative_path = os.path.relpath(btl_path, mod_dir)
            original_file_path = os.path.join(game_dir, relative_path)
            if os.path.exists(original_file_path) and not is_apk_mode:
                backup_file(original_file_path)
            shutil.copy(btl_path, original_file_path)
            print("Copied " + original_file_path + ".")

    # ---- Image files (standalone WebP) ----
    if os.path.exists(mod_image_dir):
        for pattern in ['image/**.webp', 'image/**/*.webp']:
            for file_path in glob.glob(os.path.join(mod_dir, pattern)):
                relative_path = os.path.relpath(file_path, mod_dir)
                original_file_path = os.path.join(game_dir, relative_path)
                if os.path.exists(original_file_path) and not is_apk_mode:
                    backup_file(original_file_path)
                shutil.copy(file_path, original_file_path)
                print("Copied " + original_file_path + ".")

    # ---- Atlases ----
    for pattern in ['*.png', '**/*.png', '*.webp', '**/*.webp']:
        for path in glob.glob(os.path.join(mod_dir, pattern), recursive=True):
            if not os.path.isdir(path):
                continue

            temp_folder = "temp"

            # Collect modified images
            image_paths = glob.glob(os.path.join(path, '*.png'))
            if not image_paths:
                continue

            relative_path = os.path.relpath(path, mod_dir)
            # Build the manifest path from the folder name — XML is always .xml
            # and the game always has the XML named after the .png variant
            folder_basename = os.path.basename(relative_path)
            if folder_basename.endswith('.webp'):
                folder_basename = folder_basename.replace('.webp', '.png')
            manifest_basename = folder_basename.replace('.png', '.xml')
            original_atlas_manifest_path = os.path.join(
                game_dir, os.path.dirname(relative_path), manifest_basename
            )

            if not os.path.exists(original_atlas_manifest_path):
                print(f"Warning: atlas manifest not found at {original_atlas_manifest_path}, skipping.")
                continue

            # Detect the format of the *target* game directory
            target_format = detect_atlas_format(original_atlas_manifest_path, game_dir)
            print(f"Target atlas format for {folder_basename}: {target_format}")

            # Dump the original atlas to temp to get individual PNGs
            # Returns (image_path, original_format, output_folder)
            dump_result = dump_atlas(original_atlas_manifest_path, game_dir, temp_folder)
            if dump_result is None:
                print(f"Warning: could not parse atlas manifest at {original_atlas_manifest_path}, skipping.")
                continue
            original_atlas_image_path, _, temp_working_dir = dump_result

            if not os.path.isdir(temp_working_dir):
                print(f"Warning: temp working dir not found ({temp_working_dir}), skipping.")
                continue

            # Overlay mod images
            for img_path in image_paths:
                shutil.copy2(img_path, temp_working_dir)

            # Determine the output directory in the game dir
            atlas_dir = os.path.dirname(original_atlas_manifest_path)
            base_name = os.path.basename(folder_basename)  # e.g. image_ui_hd.png
            if target_format == "WEBP":
                output_atlas_path = os.path.join(atlas_dir, base_name.replace('.png', '.webp'))
            else:
                output_atlas_path = os.path.join(atlas_dir, base_name)
            output_dir = os.path.dirname(output_atlas_path)

            # Backup originals
            if not is_apk_mode:
                if os.path.exists(original_atlas_manifest_path) and os.path.isfile(original_atlas_manifest_path):
                    backup_file(original_atlas_manifest_path)
                for ext in ('.png', '.webp'):
                    img_candidate = os.path.join(atlas_dir, base_name.replace('.png', ext))
                    if os.path.exists(img_candidate) and os.path.isfile(img_candidate):
                        backup_file(img_candidate)

            # Rebuild atlas — output format is determined by the target, not the mod source
            create_atlas_from_folder(temp_working_dir, output_dir, output_format=target_format)

            shutil.rmtree(temp_working_dir)
            print("Modified atlas " + output_atlas_path)

    return


def merge_data_file(original_path, modded_path, decrypt=False):
    if original_path.endswith(".json"):
        if decrypt:
            decrypt_file(original_path, KEY, IV)
        with open(original_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        with open(modded_path, 'r', encoding='utf-8') as f:
            modded_content = f.read()
        original_list = json.loads(original_content)
        modded_list = json.loads(modded_content)
        final_list = merge_settings(original_list, modded_list)
        final_content = json.dumps(final_list, indent=2, ensure_ascii=False)
        with open(original_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        if decrypt:
            encrypt_file(original_path, KEY, IV)

    elif original_path.endswith(".xml"):
        shutil.copy(modded_path, original_path)
        if decrypt:
            encrypt_file(original_path, KEY, IV)

    elif original_path.endswith(".ini"):
        with open(original_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        with open(modded_path, 'r', encoding='utf-8') as f:
            modded_content = f.read()
        final_content = original_content + '\n' + modded_content
        with open(original_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
    else:
        pass

    print("merged " + os.path.basename(original_path) + ".")


def merge_settings(list1, list2):
    for item in list2:
        item_id = item.get("Id", None)
        if not item_id:
            print("Warning: a modded settings Item has no Id. It will be skipped.")
            continue
        replaced = False
        for i in range(len(list1)):
            if list1[i].get("Id", None) == item_id:
                list1[i] = item
                replaced = True
                break
        if not replaced:
            list1.append(item)
    return list1


def backup_file(file_path):
    backup_path = file_path + ".backup"
    if os.path.exists(backup_path):
        return
    shutil.copy2(file_path, backup_path)


def restore_backup_file(file_path):
    original_path = file_path.removesuffix(".backup")
    shutil.copy2(file_path, original_path)


def restore_from_backups(game_dir):
    count = 0
    for file_path in glob.glob(game_dir + "**/*.backup", recursive=True):
        restore_backup_file(file_path)
        count += 1
    print("Restored " + str(count) + " files.")


def main():
    global KEY, IV
    parser = argparse.ArgumentParser(description='Main script that handles patching of files.')

    action_to_run = parser.add_mutually_exclusive_group()
    action_to_run.add_argument('-c', '--config',
                               nargs=2,
                               metavar=('KEY', 'VALUE'),
                               action=KeyValueAction,
                               help='Configure key-value pair (e.g., --config mod_directory mods/my_mod/). Can also be done by modifying config.yaml.')
    action_to_run.add_argument('-d', '--dump', action='store_true',
                               help='Dump supported moddable files in the game directory to dump/')
    action_to_run.add_argument('-p', '--patch', action='store_true',
                               help='Patches files in the configured mod directory into the game directory')
    action_to_run.add_argument('-r', '--restore', action='store_true',
                               help='Restore game to original state from backups made by this program')

    args = parser.parse_args()
    config = load_config()

    if args.config:
        update_config_items(args.config)

    game_dir = config.get("game_path")
    mod_dir = config.get("mod_directory")
    KEY = config.get('asset_key').encode() if config.get('asset_key') else None
    IV = config.get('asset_iv').encode() if config.get('asset_iv') else None

    if game_dir:
        if not config.get('mode') == "apk":
            game_dir = os.path.normpath(game_dir)
            if not game_dir.endswith(os.sep):
                game_dir = game_dir + os.sep
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
            patch_game_files(mod_dir, game_dir)
        elif config.get('mode') == "apk":
            patch_apk_files(mod_dir, game_dir)
        else:
            print("No valid mode (macOS|apk) selected. Nothing will be done.")

    os.makedirs('mods', exist_ok=True)
    return


if __name__ == '__main__':
    main()
