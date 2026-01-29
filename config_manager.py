from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
import os

yaml = YAML()
yaml.preserve_quotes = True

EMPTY_CONFIG = """# Mod Directory
mod_directory: "./mods/my_mod/"

# Working Mode (macOS|APK)
mode: macOS

# Game Path
game_path: ""

# Asset Encryption Key
asset_key: ""

# Asset IV
asset_iv: ""

#APK signing
apk_signing_enabled: true

#Keystore path
apk_keystore: ""

#keystore pass
apk_keystore_pass: ""

#Key alais
apk_key_alias: ""
"""

def create_empty_config(config_path="config.yaml"):
    file = open(config_path,"w")
    file.write(EMPTY_CONFIG)
    file.close()
    return 

def load_config(config_path="config.yaml"):
    if not os.path.exists(config_path):
        print(f"Configuration file not found when trying to load config: {config_path}. Creating file.")
        create_empty_config(config_path)

    with open(config_path, 'r') as f:
        config = yaml.load(f)
        f.close()

    return config

def update_config(config: CommentedMap, config_path: str = "config.yaml"):
    if not os.path.exists(config_path):
        print(f"Configuration file not found when trying to load config: {config_path}. Creating file.")
    
    with open(config_path, "w") as f:
        yaml.dump(config, f)
        f.close()