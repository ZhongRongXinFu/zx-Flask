import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from settings import UPLOAD_FILE_DIR
from utils.login import login_required
from utils.ai.pdfmaker import submit_convert, query_task, OFFICE_EXTS

upload_page = Blueprint('upload', __name__)

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    # 图片
    'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'},
    # 文档
    'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md', 'csv'},
    # 其他
    'other': {'zip', 'rar', '7z', 'tar', 'gz'}
}

# 最大文件大小（字节）
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

def get_file_type(filename):
    """根据文件名判断文件类型"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return file_type, ext
    
    return None, ext

def validate_file(file):
    """验证文件是否符合要求"""
    if not file or file.filename == '':
        return False, "未选择文件"
    
    # 检查文件扩展名
    file_type, ext = get_file_type(file.filename)
    if file_type is None:
        return False, f"不支持的文件类型: .{ext}"
    
    # 检查文件大小（需要读取到内存）
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # 重置文件指针
    
    if file_size > MAX_FILE_SIZE:
        return False, f"文件大小超过限制（最大 {MAX_FILE_SIZE / 1024 / 1024:.0f}MB）"
    
    return True, (file_type, ext)


def _save_file_to_path(file, absolute_path, base_dir, category, subcategory=None, subsubcategory=None, use_filename=None):
    """
    内部函数：保存文件到指定路径
    
    参数:
        - file: 文件对象
        - absolute_path: 绝对路径
        - base_dir: 基础目录
        - category: 分类
        - subcategory: 二级分类（可选）
        - subsubcategory: 三级分类（可选）
        - use_filename: 指定的文件名（不包括扩展名），扩展名将使用原始文件的扩展名。如果不提供则自动生成 UUID
    
    返回:
        - success: 是否成功
        - result: 成功时返回数据字典，失败时返回错误信息
    """
    # 验证文件
    is_valid, result = validate_file(file)
    if not is_valid:
        return False, result
    
    file_type, ext = result
    original_filename = file.filename
    
    # 确定文件名
    if use_filename:
        # 使用指定的文件名（不包括扩展名，扩展名使用原始文件的扩展名）
        unique_filename = f"{use_filename}.{ext}"
    else:
        # 自动生成 UUID
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
    
    # 构建保存路径，支持三级目录
    if subcategory and subsubcategory:
        relative_path = os.path.join(category, subcategory, subsubcategory, unique_filename)
    elif subcategory:
        relative_path = os.path.join(category, subcategory, unique_filename)
    else:
        relative_path = os.path.join(category, unique_filename)
    absolute_path = os.path.join(base_dir, relative_path)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    
    try:
        # 如果是AI聊天且文件是Office格式，自动转换为PDF
        temp_file_path = absolute_path
        is_converted = False
        
        if category == "ai-chat" and f".{ext}" in OFFICE_EXTS:
            # 先保存原始文件到临时位置
            temp_file_path = absolute_path
            file.save(temp_file_path)
            
            # 提交转换任务
            task_id = submit_convert(temp_file_path, timeout_sec=300)
            
            # 等待转换完成（最多等待300秒）
            start_time = time.time()
            max_wait = 300
            pdf_path = None
            
            while time.time() - start_time < max_wait:
                task_result = query_task(task_id)
                if task_result["ok"]:
                    if task_result["status"] == "DONE":
                        pdf_path = task_result["pdf"]
                        is_converted = True
                        break
                    elif task_result["status"] == "FAILED":
                        raise RuntimeError(f"PDF转换失败: {task_result.get('error', '未知错误')}")
                
                time.sleep(0.5)  # 每500ms检查一次
            
            if not is_converted:
                raise RuntimeError("PDF转换超时")
            
            # 删除原始文件
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            # 使用PDF文件替代原始文件
            # 修改扩展名为pdf，重新构建路径
            ext = "pdf"
            if use_filename:
                unique_filename = f"{use_filename}.pdf"
            else:
                unique_filename = f"{uuid.uuid4().hex}.pdf"
            
            if subcategory and subsubcategory:
                relative_path = os.path.join(category, subcategory, subsubcategory, unique_filename)
            elif subcategory:
                relative_path = os.path.join(category, subcategory, unique_filename)
            else:
                relative_path = os.path.join(category, unique_filename)
            
            absolute_path = os.path.join(base_dir, relative_path)
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
            
            # 移动转换后的PDF到目标位置
            import shutil
            shutil.move(pdf_path, absolute_path)
            file_type = "document"
        else:
            # 保存文件
            file.save(absolute_path)
        
        # 获取文件大小
        file_size = os.path.getsize(absolute_path)
        
        # 构建公网 URL
        url_path = relative_path.replace('\\', '/')
        public_url = f"https://static.zhongrongxinfu.cn/{url_path}"
        
        return True, {
            "filename": original_filename if not is_converted else original_filename.rsplit('.', 1)[0] + '.pdf',
            "url": public_url,
            "path": f"/{url_path}",
            "size": file_size,
            "type": file_type,
            "converted": is_converted,
            "uploaded_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        # 如果保存失败，尝试删除已创建的文件
        if os.path.exists(absolute_path):
            try:
                os.remove(absolute_path)
            except:
                pass
        
        return False, f"文件保存失败: {str(e)}"


@upload_page.route("/", methods=["POST"])
@login_required
def upload_file():
    """
    统一文件上传接口
    
    参数:
        - file: 要上传的文件（通过 multipart/form-data）
        - category: 文件分类（可选），如 'avatar', 'product', 'document', 'ai-chat' 等，用于组织存储目录
        - subcategory: 二级分类（可选），用于在 category 下创建子目录
        - filename: 自定义文件名（可选），不包含扩展名，扩展名使用原始文件的扩展名
    
    特殊处理:
        当 category=ai-chat 时，如果上传的是 Word/Excel/PowerPoint 文件，将自动转换为 PDF 后保存
        支持的Office格式: .doc, .docx, .xls, .xlsx, .ppt, .pptx
    
    返回:
        {
            "code": 200,
            "message": "上传成功",
            "data": {
                "filename": "原始文件名或转换后的PDF名",
                "url": "https://static.zhongrongxinfu.cn/uploads/xxxx.jpg",
                "path": "/uploads/xxxx.jpg",
                "size": 12345,
                "type": "image",
                "converted": false,
                "uploaded_at": "2026-01-19T10:30:00"
            }
        }
    
    使用示例:
        1. 自动生成文件名:
            POST /upload/
            file=<文件>
            category=product
        
        2. 指定文件名:
            POST /upload/
            file=<文件>
            category=product
            filename=my-product
        
        3. 使用二级目录:
            POST /upload/
            file=<文件>
            category=product
            subcategory=electronics
            filename=item-001
        
        4. 上传到AI聊天（自动转换Office文件为PDF）:
            POST /upload/
            file=<Word/Excel/PPT文件>
            category=ai-chat
            filename=my-document
            # 文件将自动转换为PDF后保存，返回的filename会是 my-document.pdf
    """
    # 获取上传的文件
    if 'file' not in request.files:
        return jsonify({"code": 400, "message": "请选择要上传的文件"}), 400
    
    file = request.files['file']
    category = request.form.get('category', 'uploads')  # 默认分类为 uploads
    subcategory = request.form.get('subcategory')  # 可选的二级分类
    subsubcategory = request.form.get('subsubcategory')  # 可选的三级分类
    custom_filename = request.form.get('filename')  # 可选的自定义文件名

    base_dir = os.path.expanduser(UPLOAD_FILE_DIR)
    success, result = _save_file_to_path(file, None, base_dir, category, subcategory=subcategory, subsubcategory=subsubcategory, use_filename=custom_filename)
    
    if not success:
        return jsonify({"code": 400, "message": result}), 400
    
    return jsonify({
        "code": 200,
        "message": "上传成功",
        "data": result
    }), 200


@upload_page.route("/batch/", methods=["POST"])
@login_required
def upload_files_batch():
    """
    批量文件上传接口
    
    参数:
        - files: 要上传的文件列表（通过 multipart/form-data）
        - category: 文件分类（可选）
        - subcategory: 二级分类（可选），用于在 category 下创建子目录
        - filenames: JSON 数组或对象，对应每个文件的自定义文件名（可选）
          格式: ["file1", "file2", "file3"] 或 "{\"0\": \"file1\", \"1\": \"file2\"}"
    
    特殊处理:
        当 category=ai-chat 时，如果上传的是 Word/Excel/PowerPoint 文件，将自动转换为 PDF 后保存
        支持的Office格式: .doc, .docx, .xls, .xlsx, .ppt, .pptx
    
    返回:
        {
            "code": 200,
            "message": "批量上传完成，成功 X 个，失败 Y 个",
            "data": {
                "success": [...],
                "failed": [...]
            }
        }
    
    使用示例:
        1. 自动生成文件名:
            POST /upload/batch/
            files=<多个文件>
            category=product
        
        2. 指定每个文件的文件名:
            POST /upload/batch/
            files=<多个文件>
            category=product
            filenames=["file1", "file2", "file3"]
        
        3. 使用二级目录:
            POST /upload/batch/
            files=<多个文件>
            category=product
            subcategory=electronics
            filenames=["item1", "item2", "item3"]
        
        4. 批量上传到AI聊天（自动转换Office文件为PDF）:
            POST /upload/batch/
            files=<多个Word/Excel/PPT文件>
            category=ai-chat
            filenames=["document1", "document2"]
            # 文件将自动转换为PDF后保存
    """
    if 'files' not in request.files:
        return jsonify({"code": 400, "message": "请选择要上传的文件"}), 400
    
    files = request.files.getlist('files')
    category = request.form.get('category', 'uploads')
    subcategory = request.form.get('subcategory')  # 可选的二级分类
    subsubcategory = request.form.get('subsubcategory')  # 可选的三级分类
    filenames_str = request.form.get('filenames')
    
    if not files:
        return jsonify({"code": 400, "message": "未找到任何文件"}), 400
    
    # 解析文件名列表
    filenames = {}
    if filenames_str:
        try:
            import json
            filenames_data = json.loads(filenames_str)
            # 支持两种格式：列表或字典
            if isinstance(filenames_data, list):
                filenames = {i: filename for i, filename in enumerate(filenames_data)}
            elif isinstance(filenames_data, dict):
                filenames = filenames_data
        except json.JSONDecodeError:
            return jsonify({"code": 400, "message": "filenames 格式错误，应为 JSON 数组或对象"}), 400
    
    success_list = []
    failed_list = []
    base_dir = os.path.expanduser(UPLOAD_FILE_DIR)
    
    for idx, file in enumerate(files):
        # 获取该文件的自定义文件名（如果有）
        custom_filename = filenames.get(str(idx)) or filenames.get(idx)
        
        success, result = _save_file_to_path(file, None, base_dir, category, subcategory=subcategory, subsubcategory=subsubcategory, use_filename=custom_filename)
        
        if success:
            success_list.append(result)
        else:
            failed_list.append({
                "filename": file.filename,
                "error": result
            })
    
    return jsonify({
        "code": 200,
        "message": f"批量上传完成，成功 {len(success_list)} 个，失败 {len(failed_list)} 个",
        "data": {
            "success": success_list,
            "failed": failed_list
        }
    }), 200


@upload_page.route("/config/", methods=["GET"])
def get_upload_config():
    """
    获取上传配置信息
    
    返回支持的文件类型、最大文件大小等配置信息
    """
    return jsonify({
        "code": 200,
        "message": "获取配置成功",
        "data": {
            "allowed_extensions": ALLOWED_EXTENSIONS,
            "max_file_size": MAX_FILE_SIZE,
            "max_file_size_mb": MAX_FILE_SIZE / 1024 / 1024,
            "base_url": "https://static.zhongrongxinfu.cn"
        }
    }), 200
