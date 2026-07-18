# World Conqueror Patcher
A script that allows dumping and patching assets and data of world conqueror 4 across versions, without needing an unlocked APK file.

## Usage
```
options:
  -h, --help            show this help message and exit
  -c KEY VALUE, --config KEY VALUE
                        Configure key-value pair (e.g., --config mod_directory mods/my_mod/ ). Can also be done by modifying config.yaml.
  -d, --dump            Dump supported moddable files in the game directory to dump/
  -p, --patch           Patches files in the configured mod directory into the game directory/APK
  -r, --restore         Restore game to original state from backups made by this program, only works in macOS mode.
```

## Installation
1. Download or clone this repository.
2. cd to the directory of this script
3. Install dependencies:

Installing the libraries in requirements.txt is required for almost all functions of the script.
```
pip install -r requirements.txt
```
If you wish to patch APKs, you need the Android SDK build tools. To install Android SDK build tools, follow these steps:

1. Download the [Android SDK command line tools](https://developer.android.com/studio#command-line-tools-only) for your operating system.
2. Unzip the downloaded files and navigate to the `bin` and `lib` folders inside.
3. Move the two folders inside a folder structure that looks like `path/to/cmdline-tools/latest/<bin and lib>`
4. Run `path/to/cmdline-tools/latest/bin/sdkmanager "build-tools;34.0.0"`. This will download the build tools in the `path/to/` folder, including the two components needed for patched APKs to be abled to be installed: zipalign and apksigner. In order to be able to use the tools via command line, you need to add `path/to/build-tools/<version number>` to the PATH environment variable.
5. Generate a keystore for signing the APK. You will be asked to enter a password and some other information which does not matter for using world conqueror patcher. Just rememeber the password as it will be needed for configuration.
```
keytool -genkeypair -v -keystore my-release-key.jks -keyalg RSA -keysize 2048 -validity 100000 -alias my-alias
```

## Configuration
After installing the dependencies, you will need to configure the script. This can be done via running
```
python main.py --configure <KEY> <VALUE>
``` 
or editing config.yaml that is generated from running the script. 
### Configuration file example

```
#Mod Directory
mod_directory: "mods/my_mod/"

#Working Mode (macOS|apk)
mode: apk

#Game Path
game_path: "/path/to/game/folder/or/apk"

#Asset Encryption Key
asset_key: "YOU NEED TO FIND A WAY TO OBTAIN THIS"

#Asset IV
asset_iv: "YOU NEED TO ALSO OBTAIN THIS"

#APK signing
apk_signing_enabled: true

#There is a part in the script that creates a debug keystore if this is not configured. 
#However, it is not recommended to rely on that as that feature is not tested.

#Keystore path
apk_keystore: "path/to/my-release-key.jks"

#keystore pass
apk_keystore_pass: "114514"

#Key alias
apk_key_alias: "test"
```

## Patching Logic
1. The script restores any backup files that exist within the directory
2. Based on matching patterns defined in schema.yaml, the script makes replacements and merges, and decrypts/re-encrypts files as needed. You may edit schema.yaml as needed.
3. replace | merge_json | merge_ini | merge_atlas | merge_xml
- replace: Directly repalces the file.
- merge_ini: Merges ini files. Literally appends user ini to the end of the existing ini, since later entries take priority.
- merge_json: Merges json files. Most if not all .json data files are in the format of a root array containing entries with unique IDs. The script repalces entries with identical IDs and adds entries with new IDs.
- merge_xml: Merges xml files. The script checks if the root tags of the xml files match, then replace entries with matching tag and at least one of the id or name attribute. 
- merge_atlas: For atalses, i.e. .png/.webp files accompanied by an .xml file in the game files or folders ending with .png/.webp in the dump, the atlas in the game files are first dissected into a folder of .pngs, then any pngs with the same names are replaced and new ones are added. The pngs are repacked into atlases, replacing the corresponding ones in the game directory.

## How to Mod
1. Configure your mode (Usually apk), game directory and mod directory with `--configure` or by editing config.yaml(generated on first run).
2. Running `--dump` is highly recommended as it provides insight into what's inside the game's folders and what can be modified. 
3. Mess around! Any supported file in your mod folder will map to the game folder.
4. To test your mod, run `--patch` and launch the game.
