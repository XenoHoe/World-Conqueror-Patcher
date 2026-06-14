import os
import glob
import rectpack

from lxml import etree
from PIL import Image


def read_wc4_atlas_xml_file(path):
    """Returns the root element tree of the file."""
    with open(path, 'r') as f:
        lines = f.readlines()

    # Easytech atlas XML has no root tag — wrap it
    xmlLines = ["<ROOT>\n"] + lines + ["</ROOT>\n"]
    root = etree.fromstring("".join(xmlLines))
    return root


def process_atlas_element_tree(path, game_dir, mod_dir):
    """
    Split an atlas file into individual PNG images.
    
    Returns (image_path, original_format, output_folder) on success, or None on failure.
    - image_path: the resolved on-disk path to the atlas image (may be .webp)
    - original_format: "PNG" or "WEBP" — the actual on-disk format
    - output_folder: the directory where the split PNGs were written
    """
    tree = read_wc4_atlas_xml_file(path)
    
    if tree[0].tag != "Texture":
        print(path, "is not an atlas file, will not parse.")
        return

    directory = os.path.dirname(path)
    xml_name_attr = tree[0].get("name")
    image_path = os.path.join(directory, xml_name_attr)

    # Determine actual on-disk format (APK builds ship WebP but XML says .png)
    original_format = "WEBP" if image_path.endswith(".webp") else "PNG"
    if not (os.path.exists(image_path) and os.path.isfile(image_path)):
        if image_path.endswith(".png"):
            print(image_path, "does not exist, trying .webp fallback...")
            webp_path = image_path.replace('.png', '.webp')
            if os.path.exists(webp_path) and os.path.isfile(webp_path):
                image_path = webp_path
                original_format = "WEBP"
            else:
                print(image_path, "neither .png nor .webp found, will not process.")
                return
        else:
            print(image_path, "is not a png or webp file, implying non-standard format. Will not process.")
            return

    # Warn modders about the XML vs disk mismatch
    if xml_name_attr.endswith(".png") and original_format == "WEBP":
        print(f"Note: XML references '{xml_name_attr}' but actual asset is WebP — using WebP as original format.")

    atlas_image = Image.open(image_path)

    relative_dir = os.path.relpath(os.path.dirname(path), game_dir)
    # Use the XML-declared name (.png) for the folder regardless of actual format,
    # so mod folders are consistent across platforms
    folder_name = xml_name_attr if xml_name_attr.endswith(".png") else os.path.basename(image_path)
    output_folder = os.path.join(mod_dir, relative_dir, folder_name)
    os.makedirs(output_folder, exist_ok=True)

    # Persist the original on-disk format so downstream knows how to repack
    format_path = os.path.join(output_folder, ".atlas_format")
    with open(format_path, "w") as f:
        f.write(original_format + "\n")

    for image_data in tree[1]:
        read_and_save_atlas_region(atlas_image, image_data, output_folder)

    return image_path, original_format, output_folder


def read_and_save_atlas_region(atlas_image, data, target_dir="temp"):
    name = data.get("name")
    x = int(data.get("x"))
    y = int(data.get("y"))
    w = int(data.get("w"))
    h = int(data.get("h"))
    new_img = atlas_image.crop((x, y, x + w, y + h))
    new_img.save(os.path.join(target_dir, name), "PNG")


def create_atlas_from_folder(path, target_dir="temp/image_outputs/", output_format=None):
    """
    Rebuild an atlas image + XML manifest from a folder of individual PNGs.
    
    Args:
        path: Folder containing the individual PNG images.
        target_dir: Directory to write the final atlas image and XML into.
        output_format: "PNG" or "WEBP". If None, auto-detect from
                       .atlas_format metadata file, then fall back to
                       inferring from the folder name suffix.
    """
    if not os.path.isdir(path):
        return

    os.makedirs(target_dir, exist_ok=True)

    # Resolve output format: explicit arg > .atlas_format metadata > folder suffix
    if output_format is None:
        format_path = os.path.join(path, ".atlas_format")
        if os.path.exists(format_path):
            with open(format_path) as f:
                output_format = f.read().strip()
    if output_format is None:
        # Legacy fallback
        output_format = "WEBP" if path.endswith(".webp") else "PNG"

    is_webp = (output_format == "WEBP")

    # The XML manifest always references a .png name regardless of actual format
    folder_name = os.path.basename(path.rstrip('/'))
    if is_webp and folder_name.endswith(".webp"):
        folder_name = folder_name.replace(".webp", ".png")
    final_filename = os.path.join(target_dir, folder_name)
    print("Rebuilding atlas:", final_filename)

    # Read individual PNGs
    image_pattern = os.path.join(path, "*.png")
    file_paths = glob.glob(image_pattern)
    images = {}
    for file_path in file_paths:
        img = Image.open(file_path)
        images[os.path.basename(file_path)] = img

    if not images:
        print("No PNGs found in", path, "— nothing to pack.")
        return

    # Pack rectangles
    packer = rectpack.newPacker(rotation=False)
    packer.add_bin(1024, 2048)
    for key in images:
        # 1px padding on top/left as seen in Easytech XML
        packer.add_rect(images[key].width + 1, images[key].height + 1, key)
    packer.pack()

    all_rects = packer.rect_list()
    placements = {}
    maxheight = 0
    for rect in all_rects:
        b, x, y, w, h, rid = rect
        placements[rid] = (x + 1, y + 1, w - 1, h - 1)
        if y + h > maxheight:
            maxheight = y + h

    # Build final image and XML manifest
    final_image = Image.new("RGBA", (1024, maxheight), (0, 0, 0, 0))
    texture_root = etree.Element("Texture", name=os.path.basename(final_filename))
    images_root = etree.Element("Images")

    for key in images:
        if key in placements:
            x, y, w, h = placements[key]
            final_image.paste(images[key], (x, y))
            etree.SubElement(
                images_root, "Image",
                name=key, x=str(x), y=str(y), w=str(w), h=str(h),
                refx="0", refy="0"
            )

    # Save atlas in the target format
    if is_webp:
        # Save image as WebP with .webp extension (the game reads this)
        # but keep the XML referencing the .png name
        final_image.save(final_filename.replace('.png', '.webp'), "WEBP")
        xml_filename = final_filename.replace('.png', '.xml')
    else:
        final_image.save(final_filename, "PNG")
        xml_filename = final_filename.replace('.png', '.xml')

    manifest_text = xml_to_string(texture_root) + xml_to_string(images_root)
    with open(xml_filename, 'w', encoding='utf-8') as f:
        f.write(manifest_text)

    # Clean up metadata marker in working dir
    temp_meta = os.path.join(path, ".atlas_format")
    if os.path.exists(temp_meta):
        os.remove(temp_meta)

    for key in images:
        images[key].close()


def xml_to_string(element, **kwargs):
    return etree.tostring(element, pretty_print=True, **kwargs).decode()
