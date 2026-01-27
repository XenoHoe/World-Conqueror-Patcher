import os
import glob
import rectpack

from lxml import etree
from PIL import Image





def read_wc4_atlas_xml_file(path):
    #Returns the root element tree of the file.

    file = open(path,'r')
    lines = file.readlines()
    file.close()

    xmlLines = ["<ROOT>\n"] + lines + ["</ROOT>\n"]#Because, for whatever godforsaken reason, the easytech atlas xml is actually illegal with no root tag.
    
    xmlStr = ""

    for line in xmlLines:
        xmlStr += line
    
    root = etree.fromstring(xmlStr)

    return root

def process_atlas_element_tree(path,game_dir,mod_dir):
    tree = read_wc4_atlas_xml_file(path)
    
    if tree[0].tag != "Texture":
        print(path,"is not an atlas file, will not parse.")
        return

    directory = os.path.dirname(path)
    image_path = os.path.join(directory,tree[0].get("name"))

    if not(os.path.exists(image_path) and os.path.isfile(image_path)):
        print(image_path,"does not exist or is not a file, will not parse.")
        return

    atlas_image = Image.open(image_path)

    relative_dir = os.path.relpath(os.path.dirname(path),game_dir)
    target_dir = os.path.join(mod_dir,relative_dir,os.path.basename(image_path))
    
    os.makedirs(target_dir,exist_ok=True)

    for image_data in tree[1]:
        read_and_save_atlas_region(atlas_image,image_data,target_dir)


    return

def read_and_save_atlas_region(atlas_image,data,target_dir="temp"):
    name,x,y,w,h = data.get("name"),int(data.get("x")),int(data.get("y")),int(data.get("w")),int(data.get("h"))
    left,top,right,bottom=x,y,x+w,y+h


    new_img = atlas_image.crop((left,top,right,bottom))

    new_img.save(os.path.join(target_dir,name),"PNG")

    return


def create_atlas_from_folder(path,target_dir="temp/image_outputs/"):
    if not os.path.isdir(path):#Incase that happens
        return
    #Reading Images
    os.makedirs(target_dir,exist_ok=True)
    image_pattern = os.path.join(path,"*.png")
    file_paths = glob.glob(image_pattern)
    if not path.removesuffix("/").endswith(".png"):
        path = path.removesuffix("/") + ".png/"

    final_filename = os.path.join(target_dir,os.path.basename(path.removesuffix('/')))
    #print(final_filename)
    images = {}

    for file_path in file_paths:
        image = Image.open(file_path)
        images[os.path.basename(file_path)] = image

    #Packing Images
    packer = rectpack.newPacker(rotation=False)

    packer.add_bin(1024,2048)

    for key in images:
        packer.add_rect(images[key].width+1,images[key].height+1,key)#In the XML files the seems to be padded by 1 px on top and left

    packer.pack()

    all_rects = packer.rect_list()
    placements = {}
    maxheight = 0
    for rect in all_rects:
        b, x, y, w, h, rid = rect
        #print("File Name:",rid,"X:",x+1,"Y:",y+1,"W:",w-1,"H",h-1)
        placements[rid] = (x+1,y+1,w-1,h-1)
        maxheight = y+h if y+h>= maxheight else maxheight

    #Creating final image and manifest xml
    final_image = Image.new("RGBA",(1024,maxheight),(0,0,0,0))
    TextureRoot = etree.Element("Texture",name=os.path.basename(final_filename))
    ImageRoot = etree.Element("Images")

    for key in images:
        if key in placements:
            x, y, w, h = placements[key]
            final_image.paste(images[key], (x, y))
            etree.SubElement(ImageRoot,"Image",name=key,x=str(x),y=str(y),w=str(w),h=str(h),refx="0",refy="0")

    final_image.save(final_filename,"PNG")
    
    manifest_text = xml_to_string(TextureRoot) + xml_to_string(ImageRoot)
    file = open(final_filename.replace('.png','.xml'),'w')
    file.write(manifest_text)
    file.close()
    return

def xml_to_string(element, **kwargs):
    return etree.tostring(element, pretty_print=True, **kwargs).decode()

#create_atlas_from_folder("temp/image_general_medal_hd.png/")
