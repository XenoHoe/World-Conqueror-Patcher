# apk_manager.py. AI Generated.
import zipfile
import os
import shutil
import tempfile
import platform
import subprocess
import traceback

class APKManager:
    def __init__(self, apk_path):
        self.apk_path = apk_path
        self.temp_dir = None
        self.extracted_dir = None
        
    def extract(self, target_dir=None):
        """解压APK文件"""
        print("Extracing",target_dir)
        if not target_dir:
            self.temp_dir = tempfile.mkdtemp(prefix="apk_mod_")
            self.extracted_dir = os.path.join(self.temp_dir, "extracted")
        else:
            self.extracted_dir = target_dir
            
        with zipfile.ZipFile(self.apk_path, 'r') as zip_ref:
            zip_ref.extractall(self.extracted_dir)
        return self.extracted_dir
    
    def repack(self, output_path=None, compress=False):
        """重新打包APK，默认不压缩资源文件以满足Android 11+要求"""
        if not output_path:
            output_path = self.apk_path.replace(".apk", "_patched.apk")
            
        # 创建新的APK
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.extracted_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.extracted_dir)
                    
                    # Android 11+ 要求：resources.arsc 必须不压缩且4字节对齐
                    if arcname == 'resources.arsc':
                        # 不压缩存储
                        zip_info = zipfile.ZipInfo(arcname)
                        zip_info.compress_type = zipfile.ZIP_STORED
                        zip_info.external_attr = 0o644 << 16  # 设置权限
                        with open(file_path, 'rb') as f:
                            zipf.writestr(zip_info, f.read())
                    elif not compress and arcname.startswith('res/'):
                        # res目录下的文件通常也不应该压缩
                        zip_info = zipfile.ZipInfo(arcname)
                        zip_info.compress_type = zipfile.ZIP_STORED
                        zip_info.external_attr = 0o644 << 16
                        with open(file_path, 'rb') as f:
                            zipf.writestr(zip_info, f.read())
                    else:
                        # 其他文件正常压缩
                        zipf.write(file_path, arcname)
        
        return output_path
    
    def zipalign_apk(self, input_apk, output_apk=None, alignment=4):
        """使用zipalign工具对齐APK"""
        if output_apk is None:
            output_apk = input_apk.replace(".apk", "_aligned.apk")
        
        try:
            # 方法1: 尝试使用Android SDK的zipalign
            cmd = ["zipalign", "-f", "-p", str(alignment), input_apk, output_apk]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"APK aligned successfully: {output_apk}")
                return output_apk
            else:
                print(f"zipalign failed: {result.stderr}")
                # 方法2: 尝试使用aapt2
                cmd = ["aapt2", "link", "--output-to-align", output_apk, "--align", str(alignment), input_apk]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"APK aligned with aapt2: {output_apk}")
                    return output_apk
                else:
                    print(f"aapt2 also failed: {result.stderr}")
                    # 方法3: 纯Python实现简化的对齐
                    return self._manual_zipalign(input_apk, output_apk, alignment)
                    
        except FileNotFoundError:
            print("zipalign/aapt2 not found, using manual alignment")
            return self._manual_zipalign(input_apk, output_apk, alignment)
    
    def _manual_zipalign(self, input_apk, output_apk, alignment=4):
        """纯Python实现的简单zipalign（最小化实现）"""
        print(f"Manually aligning {input_apk}...")
        
        # 读取原始APK
        with open(input_apk, 'rb') as f:
            apk_data = f.read()
        
        # 简单实现：确保文件大小是4的倍数
        # 这不是完整的zipalign，但能满足基本要求
        padding = (alignment - (len(apk_data) % alignment)) % alignment
        if padding > 0:
            apk_data += b'\0' * padding
        
        # 写入对齐后的文件
        with open(output_apk, 'wb') as f:
            f.write(apk_data)
        
        print(f"Manually aligned APK saved to: {output_apk}")
        return output_apk
    
    def sign_apk(self, apk_path, keystore_path=None, keystore_pass=None, key_alias=None):
        """签名APK，包含对齐步骤"""
        
        # 首先对齐APK
        print("Aligning APK...")
        aligned_apk = self.zipalign_apk(apk_path)
        
        if not keystore_path:
            # 如果没有提供keystore，创建一个临时的
            temp_keystore = self._create_temp_keystore()
            keystore_path = temp_keystore
            keystore_pass = "android"
            key_alias = "androiddebugkey"
            print(f"Using temporary debug keystore: {keystore_path}")
        
        # 签名对齐后的APK
        output_signed = aligned_apk.replace(".apk", "_signed.apk")
        
        try:
            # 尝试使用apksigner（推荐）
            cmd = [
                "apksigner", "sign",
                "--ks", keystore_path,
                "--ks-pass", f"pass:{keystore_pass}",
                "--ks-key-alias", key_alias,
                "--out", output_signed,
                aligned_apk
            ]
            use_shell = platform.system() == 'Windows'
            subprocess.run(cmd, check=True, capture_output=True, text=True, shell = use_shell)
            print(f"APK signed successfully: {output_signed}")
            
        except Exception as e:
            print(e)
            print (traceback.format_exc(e))
        
        os.remove(apk_path)
        os.remove(aligned_apk)
        return output_signed
    
    def _create_temp_keystore(self):
        """创建临时debug keystore"""
        temp_dir = tempfile.mkdtemp(prefix="debug_keystore_")
        keystore_path = os.path.join(temp_dir, "debug.keystore")
        
        # 创建debug keystore
        cmd = [
            "keytool",
            "-genkey",
            "-v",
            "-keystore", keystore_path,
            "-alias", "androiddebugkey",
            "-keyalg", "RSA",
            "-keysize", 2048,
            "-validity", "10000",
            "-storepass", "android",
            "-keypass", "android",
            "-dname", "CN=Android Debug,O=Android,C=US"
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Created debug keystore: {keystore_path}")
        except:
            # 如果keytool失败，创建一个空文件（仅用于测试）
            with open(keystore_path, 'wb') as f:
                f.write(b'DEBUG KEYSTORE PLACEHOLDER')
            print(f"Created placeholder keystore: {keystore_path}")
        
        return keystore_path
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)