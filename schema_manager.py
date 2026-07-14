from ruamel.yaml import YAML
import os

yaml = YAML()
yaml.preserve_quotes = True

DEFAULT_SCHEMA = """# Patch Schema
# Defines what files to dump from the game and how to patch them back.
#
# dump entries:
#   pattern: glob pattern relative to game directory
#   action: copy | atlas
#   decrypt: true/false (optional, default false)
#
# patch entries:
#   pattern: glob pattern relative to mod directory
#   action: replace | merge_json | merge_ini | merge_atlas | merge_xml
#   decrypt: true/false (optional, default false)
#   match: file | directory (optional, default file)

dump:
  - pattern: "data/*.json"
    action: copy
    decrypt: true
  - pattern: "data/*.xml"
    action: copy
    decrypt: true
  - pattern: "*.ini"
    action: copy
  - pattern: "stage/*.btl"
    action: copy
  - pattern: "image/**/*.webp"
    action: copy
  - pattern: "**/*.xml"
    action: atlas

patch:
  - pattern: "data/*.json"
    action: merge_json
    decrypt: true
  - pattern: "data/*.xml"
    action: merge_xml
    decrypt: true
  - pattern: "*.ini"
    action: merge_ini
  - pattern: "stage/**/*.btl"
    action: replace
  - pattern: "image/**/*.webp"
    action: replace
  - pattern: "**/*.png"
    action: merge_atlas
    match: directory
  - pattern: "**/*.webp"
    action: merge_atlas
    match: directory
"""


def create_default_schema(schema_path="schema.yaml"):
    with open(schema_path, "w") as f:
        f.write(DEFAULT_SCHEMA)


def load_schema(schema_path="schema.yaml"):
    if not os.path.exists(schema_path):
        print(f"Schema file not found: {schema_path}. Creating default schema.")
        create_default_schema(schema_path)

    with open(schema_path, 'r') as f:
        schema = yaml.load(f)

    return schema
