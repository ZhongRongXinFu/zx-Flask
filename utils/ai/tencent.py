from settings import AI_TENCENT_SECRET_ID, AI_TENCENT_SECRET_KEY
import json

# import tencentcloud.common.exception.tencent_cloud_sdk_exception as exce
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models


def upload_file_to_hunyuan(file_name: str, file_url: str) -> str:
    cred = credential.Credential(AI_TENCENT_SECRET_ID, AI_TENCENT_SECRET_KEY)

    http_profile = HttpProfile()
    http_profile.endpoint = "hunyuan.tencentcloudapi.com"

    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile

    client = hunyuan_client.HunyuanClient(cred, "ap-shanghai", client_profile)

    req = models.FilesUploadsRequest()
    params = {
        "Name": file_name,   # 随便起名，方便自己识别
        "URL": file_url      # 你在 COS 等地方的文件直链
    }
    req.from_json_string(json.dumps(params))

    resp = client.FilesUploads(req)
    data = json.loads(resp.to_json_string())
    file_id = data["ID"]   # 例如 "file-YbhlphnNEsjRoKTEXukAqNZZ"
    print("上传成功，file_id:", file_id)
    return file_id

def create_thread_with_file(file_id: str) -> str:
    cred = credential.Credential(AI_TENCENT_SECRET_ID, AI_TENCENT_SECRET_KEY)
    http_profile = HttpProfile()
    http_profile.endpoint = "hunyuan.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = hunyuan_client.HunyuanClient(cred, "ap-shanghai", client_profile)

    req = models.CreateThreadRequest()

    # 注意：下面这个结构是“示意”，字段名以 SDK 自动生成的为准，
    # 实战时可以在 API Explorer 里选择 Python，复制它给你的代码，然后把 file_id 填进去。
    params = {
        "ToolResources": {
            "CodeInterpreter": [file_id]
        }
    }
    req.from_json_string(json.dumps(params))

    resp = client.CreateThread(req)
    data = json.loads(resp.to_json_string())
    thread_id = data["ID"]
    print("创建会话成功，thread_id:", thread_id)
    return thread_id

def run_thread(thread_id: str, file_id: str, question: str):
    cred = credential.Credential(AI_TENCENT_SECRET_ID, AI_TENCENT_SECRET_KEY)
    http_profile = HttpProfile()
    http_profile.endpoint = "hunyuan.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = hunyuan_client.HunyuanClient(cred, "ap-shanghai", client_profile)

    req = models.RunThreadRequest()
    params = {
        "Model": "hunyuan-turbos-latest",
        "ThreadID": thread_id,
        "Stream": True,
        "AdditionalMessages": [
            {
                "Role": "user",
                "Attachments": [
                    {"FileID": file_id}   # 关键就这一行
                ],
                "Content": question  # 你的 prompt，例如：请根据绑定的文件，帮我总结主要风险点
            }
        ]
    }
    req.from_json_string(json.dumps(params))

    # RunThread 是 SSE 流式接口，SDK 这边会给出对应的流式读取方法，
    # 实际用法请在 API Explorer 中选择“Python”，查看生成的示例。
    resp = client.RunThread(req)

    full_text = ""

    for event in resp:
        # 现在 event 是一个 dict: {"event": "...", "data": "...json 字符串..."}
        if not isinstance(event, dict):
            continue

        # 只处理内容增量事件，其他类型可以先忽略
        if event.get("event") != "thread.message.delta":
            continue

        data_str = event.get("data")
        if not data_str:
            continue

        try:
            data = json.loads(data_str)
        except Exception:
            # data 不是合法 json 的话直接跳过
            continue

        # data 结构:
        # {
        #   "ID": "...",
        #   "Object": "thread.message.delta",
        #   "Delta": {
        #       "Content": [
        #           {
        #               "Index": 0,
        #               "Type": "text",
        #               "Text": {
        #                   "Value": "张"
        #               }
        #           }
        #       ]
        #   }
        # }
        delta = data.get("Delta", {})
        contents = delta.get("Content", [])

        for item in contents:
            if item.get("Type") != "text":
                continue
            value = item.get("Text", {}).get("Value", "")
            if not value:
                continue

            # 累加到完整结果里
            full_text += value

            # 如果你想在控制台边收边打印，就保留这一行
            print(value, end="", flush=True)

    print("\n\n=== 最终汇总内容 ===")
    print(full_text)
    return full_text

def chat(prompt, think, file_url="https://static.ksuser.cn/temp/p/FinanceFile_20251010171353.pdf"):
    file_id = upload_file_to_hunyuan("个人信用报告.pdf", file_url)
    thread_id = create_thread_with_file(file_id)
    return run_thread(thread_id, file_id, prompt)

if __name__ == "__main__":
    chat()


    file_id = upload_file_to_hunyuan("个人信用报告.pdf", "https://static.ksuser.cn/temp/p/FinanceFile_20251010171353.pdf")
    # print(file_id)
    # file_id=  "file-bDPlwi2mss03OywTHoj2SSyD"
    thread_id = create_thread_with_file(file_id)
    # thread_id= "thread_KOYytQsCNnBKLfM6xYhwNngP"
    run_thread(thread_id, file_id,  """基础信息提取：从个人信用报告中提取客户姓名；根据报告内客户身份证号（第 7-14 位出生日期），结合报告生成时间，计算并明确客户年龄（需标注计算逻辑：报告生成年份 - 出生年份）。
未结清贷款信息整理：仅统计客户本人未结清的贷款，已结清部分无需列出。按 “银行名称 + 未结清贷款余额（单位：万元）” 的格式生成文字清单，同时核算未结清贷款总和（单位：万元）。
核验要求：需对照报告中 “信贷交易授信及负债信息概要”，将循环贷账户余额与非循环贷账户余额相加，确认计算出的贷款总和与该概要数据一致；同时核验未结清贷款涉及的管理机构数量，确保等于非循环贷管理机构数与循环贷账户管理机构数之和。
未结清担保信息整理：仅统计客户未结清的担保责任，按 “序号 + 银行名称（同一银行的多笔担保合并为一笔，需注明合并笔数）+ 未结清担保余额（单位：万元）” 的格式生成文字清单，标注序号并按担保业务发生时间先后排序，同时核算未结清担保总和（单位：万元）。
计算要求：每笔担保余额需精准对应报告中 “截至特定日期的余额” 数据，合并同一银行的多笔余额时需重复核验加法计算，确保无计算错误。
最终校验：所有数据（姓名、年龄、贷款余额及总和、担保余额及总和、机构数量）均需与报告原文逐一对标，确保无遗漏、无错算、无概念混淆（如区分 “相关还款责任金额” 与 “未结清担保余额”，仅用后者计算）""")