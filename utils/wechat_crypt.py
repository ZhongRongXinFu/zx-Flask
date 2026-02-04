"""
微信消息加密解密工具类
实现微信消息的AES加密/解密、签名验证等功能
"""

import base64
import hashlib
import struct
import os
from Crypto.Cipher import AES


class WXBizMsgCrypt:
    """微信消息加密解密类"""
    
    def __init__(self, token, encoding_aes_key, appid):
        """
        初始化
        
        Args:
            token: 微信配置的Token
            encoding_aes_key: 微信配置的EncodingAESKey (43位)
            appid: 小程序AppID
        """
        self.token = token
        self.appid = appid
        
        # EncodingAESKey补"="后进行base64解码得到32字节的AESKey
        self.aes_key = base64.b64decode(encoding_aes_key + "=")
        
        # AES CBC模式，IV使用AESKey的前16字节
        self.iv = self.aes_key[:16]
    
    def verify_signature(self, signature_str, timestamp, nonce, encrypt_msg):
        """
        验证msg_signature签名
        
        Args:
            signature_str: URL参数中的msg_signature
            timestamp: URL参数中的timestamp
            nonce: URL参数中的nonce
            encrypt_msg: POST包体中的Encrypt字段
            
        Returns:
            bool: 签名是否正确
        """
        # 1. 将token、timestamp、nonce、encrypt_msg进行字典序排序
        params = sorted([self.token, timestamp, nonce, encrypt_msg])
        
        # 2. 拼接字符串
        concat_str = ''.join(params)
        
        # 3. SHA1计算签名
        signature = hashlib.sha1(concat_str.encode('utf-8')).hexdigest()
        
        # 4. 对比签名
        return signature == signature_str
    
    def decrypt(self, encrypt_msg):
        """
        解密消息
        
        Args:
            encrypt_msg: 加密的消息体（Encrypt字段）
            
        Returns:
            tuple: (success, msg, appid) 
                   success: 是否成功
                   msg: 解密后的明文消息
                   appid: 消息中的appid
        """
        try:
            # 1. Base64解码密文
            cipher_text = base64.b64decode(encrypt_msg)
            
            # 2. AES解密
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
            decrypted = cipher.decrypt(cipher_text)
            
            # 3. 去除PKCS#7填充
            pad = decrypted[-1]
            if isinstance(pad, str):
                pad = ord(pad)
            decrypted = decrypted[:-pad]
            
            # 4. 解析：random(16B) + msg_len(4B) + msg + appid
            # 跳过前16字节的随机字符串
            content = decrypted[16:]
            
            # 读取msg_len（网络字节序，4字节）
            msg_len = struct.unpack('>I', content[:4])[0]
            
            # 提取消息内容
            msg = content[4:4+msg_len].decode('utf-8')
            
            # 提取appid
            from_appid = content[4+msg_len:].decode('utf-8')
            
            # 5. 验证appid
            if from_appid != self.appid:
                return False, None, from_appid
            
            return True, msg, from_appid
            
        except Exception as e:
            print(f"解密失败: {str(e)}")
            return False, None, None
    
    def encrypt(self, reply_msg):
        """
        加密回包消息
        
        Args:
            reply_msg: 明文回包内容
            
        Returns:
            str: 加密后的密文（Base64编码）
        """
        try:
            # 1. 生成16字节随机字符串
            random_str = os.urandom(16)
            
            # 2. 计算msg长度（网络字节序）
            msg_bytes = reply_msg.encode('utf-8')
            msg_len = struct.pack('>I', len(msg_bytes))
            
            # 3. 构造FullStr = random(16B) + msg_len(4B) + msg + appid
            appid_bytes = self.appid.encode('utf-8')
            full_str = random_str + msg_len + msg_bytes + appid_bytes
            
            # 4. PKCS#7填充
            block_size = 32
            padding_len = block_size - len(full_str) % block_size
            padding = bytes([padding_len] * padding_len)
            full_str_padded = full_str + padding
            
            # 5. AES加密
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
            encrypted = cipher.encrypt(full_str_padded)
            
            # 6. Base64编码
            return base64.b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            print(f"加密失败: {str(e)}")
            return None
    
    def generate_signature(self, timestamp, nonce, encrypt_msg):
        """
        生成回包的msg_signature
        
        Args:
            timestamp: 时间戳
            nonce: 随机数
            encrypt_msg: 加密的消息
            
        Returns:
            str: msg_signature签名
        """
        # 将token、timestamp、nonce、encrypt_msg进行字典序排序
        params = sorted([self.token, str(timestamp), nonce, encrypt_msg])
        
        # 拼接字符串
        concat_str = ''.join(params)
        
        # SHA1计算签名
        return hashlib.sha1(concat_str.encode('utf-8')).hexdigest()
