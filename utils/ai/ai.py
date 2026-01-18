import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json, re, os, subprocess, uuid
from datetime import datetime
from pdf2image import convert_from_path
from settings import *
from openai import OpenAI
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

def validate_prompt(prompt):
    if not prompt:
        return False, "提示词不能为空"
    if len(prompt) > 2000:
        return False, "提示词过长（> 2000 字符）"
    if not re.compile(r'^[\u4e00-\u9fffA-Za-z0-9\s，。、“”"\'！？,.!?：:；;()\[\]\-_/]+$').match(prompt):
        return False, "提示词含有不被允许的特殊字符"
    return True, None

def validate_file_ext(filename: str):
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".pdf", ".doc", ".docx", ".xls", ".xlsx"}:
        return False, "只允许上传图片/pdf/word/excel文件"
    return True, ext

def validate_file_size(file_storage):
    # 获取当前指针位置
    pos = file_storage.stream.tell()
    # 移到末尾计算大小
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    # 复位指针
    file_storage.stream.seek(pos, os.SEEK_SET)

    if size > 3 * 1024 * 1024:
        return False, "文件大小不能超过 3MB"
    return True, size

def save_temp_file(file_storage, ext: str) -> str:
    """把上传的文件先保存到临时目录，返回临时路径"""
    date_str = datetime.now().strftime("%Y%m%d")
    uid = uuid.uuid4().hex
    tmp_filename = f"{date_str}_{uid}{ext}"
    tmp_path = os.path.join("./temp/", tmp_filename)
    file_storage.save(tmp_path)
    return tmp_path

def office_to_pdf(input_path: str) -> str:
    """
    使用 LibreOffice 把 Word / Excel 转成 PDF
    要求服务器已安装: libreoffice
    """
    # 输出到同一目录
    out_dir = os.path.dirname(input_path)
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", out_dir,
        input_path,
    ]
    subprocess.run(cmd, check=True)

    base, _ = os.path.splitext(input_path)
    pdf_path = base + ".pdf"
    if not os.path.exists(pdf_path):
        raise RuntimeError("Office 转 PDF 失败，未找到输出文件")
    return pdf_path


def pdf_to_images(pdf_path: str, out_dir: str, base_name: str) -> list[str]:
    """
    把 PDF 每一页转成一张 PNG 图片，返回文件名列表
    base_name 用于生成形如：20251130_xxx_p1.png
    """
    # dpi 可以按需求调高，dpi 越大越清晰也越大
    pages = convert_from_path(pdf_path, dpi=200)
    filenames = []
    for i, page in enumerate(pages, start=1):
        img_name = f"{base_name}_p{i}.png"
        img_path = os.path.join(out_dir, img_name)
        page.save(img_path, "PNG")
        filenames.append(img_name)
    return filenames

def deepseek_chat(prompt:str="写一段关于 Python 的小介绍。", think="disabled"):
    client = OpenAI(
        api_key=AI_DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

    stream = client.chat.completions.create(
        model="deepseek-chat",
        extra_body={"thinking": {"type": think}},
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=True,  # 开启流式
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content

def hunyuan_chat(prompt):
    try:
        # 实例化一个认证对象，入参需要传入腾讯云账户secretId，secretKey
        cred = credential.Credential(
            AI_TENCENT_SECRET_ID,
            AI_TENCENT_SECRET_KEY)

        cpf = ClientProfile()
        # 预先建立连接可以降低访问延迟
        cpf.httpProfile.pre_conn_pool_size = 3
        client = hunyuan_client.HunyuanClient(cred, "", cpf)

        req = models.ChatCompletionsRequest()
        req.Model = "hunyuan-lite"
        msg = models.Message()
        msg.Role = "user"
        msg.Content = prompt

        req.Messages = [msg]
        req.Stream = True
        resp = client.ChatCompletions(req)

        for event in resp:
            # print(event["data"])
            data = json.loads(event['data'])
            for choice in data['Choices']:
                yield choice['Delta']['Content']
    except TencentCloudSDKException as err:
        yield str(err)

if __name__ == "__main__":
    for chunk in hunyuan_chat("写一段关于 Python 的小介绍。"):
        print(chunk, end='', flush=True)