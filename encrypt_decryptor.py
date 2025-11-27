from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from Crypto.Util.Padding import pad
from hashlib import md5
import argparse
import traceback

KEY = b"BYPFO2387HLKNJEODFUD9TU8HUB445HS"
IV = b"SF3WRA3SDF3VFDD9"


def decrypt_file_aes_cbc(file_path, key, iv):
    """
    Remove first 20 bytes from file and decrypt the rest using AES CBC mode.
    Replace file content with decrypted text.
    """
    try:
        with open(file_path, 'rb') as file:
            content = file.read()
        
        # Remove first 20 bytes
        if len(content) <= 20:
            print(f"Warning: File {file_path} is too short (<= 20 bytes), skipping")
            return False
            
        encrypted_data = content[20:]
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        decrypted_data = cipher.decrypt(encrypted_data)
        
        unpadded_data = unpad(decrypted_data, AES.block_size)
        
        # Write decrypted content back to file
        with open(file_path, 'wb') as file:
            file.write(unpadded_data)
        
        print(f"Decrypted: {file_path}")
        return True
        
    except Exception as e:
        print(f"Error decrypting file {file_path}: {e}")
        print(traceback.format_exc())
        return False

def encrypt_file_aes_cbc(file_path,key,iv):
    """
    Assuming plaintext file,
    Replace file content with packaged data format.
    """
    try:
        with open(file_path, 'rb') as file:
            content = file.read()
        #Because the stupid game only reads CRLF
        content = normalize_to_crlf(content)
        #Get length
        length = len(content).to_bytes(4, byteorder='little')
        #Get hash
        hash = md5(content).digest()
        #Encryption sequence
        content = pad(content,16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(content)
        #Assemble final file
        final_file = hash + length + encrypted_data
        #Write file
        with open(file_path, 'wb') as file:
            file.write(final_file)
        
        print(f"Encrypted and packaged: {file_path}")

        return True
    
    except Exception as e:
        print(f"Error encrypting file {file_path}: {e}")
        print(traceback.format_exc())
        return False


def normalize_to_crlf(content):
    return content.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

def main():
    parser = argparse.ArgumentParser(description='Script that handles encrypting and decrypting of data')
    
    parser.add_argument('input_file', help='Path to the input file')

    action_to_run = parser.add_mutually_exclusive_group()

    action_to_run.add_argument('-e', '--encrypt', action='store_true', help='Encryption mode, mutually exlusive with -d')
    action_to_run.add_argument('-d', '--decrypt', action='store_true', help='Decryption mode, mutually exlusive with -e')

    args = parser.parse_args()

    if args.encrypt:
        encrypt_file_aes_cbc(args.input_file,KEY,IV)
    elif args.decrypt:
        decrypt_file_aes_cbc(args.input_file,KEY,IV)
    else:
        print("Mode not selected, quitting")
        return

if __name__ == "__main__":
    main()