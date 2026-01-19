import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from settings import UPLOAD_FILE_DIR
from utils.login import login_required

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


def _save_file_to_path(file, absolute_path, base_dir, category, use_filename=None):
    """
    内部函数：保存文件到指定路径
    
    参数:
        - file: 文件对象
        - absolute_path: 绝对路径
        - base_dir: 基础目录
        - category: 分类
        - use_filename: 指定的文件名（包括扩展名），如果不提供则自动生成
    
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
        # 使用指定的文件名（完整文件名）
        unique_filename = use_filename
    else:
        # 自动生成 UUID
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
    
    # 构建保存路径
    relative_path = os.path.join(category, unique_filename)
    absolute_path = os.path.join(base_dir, relative_path)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    
    try:
        # 保存文件
        file.save(absolute_path)
        
        # 获取文件大小
        file_size = os.path.getsize(absolute_path)
        
        # 构建公网 URL
        url_path = relative_path.replace('\\', '/')
        public_url = f"https://static.zhongrongxinfu.cn/{url_path}"
        
        return True, {
            "filename": original_filename,
            "url": public_url,
            "path": f"/{url_path}",
            "size": file_size,
            "type": file_type,
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
        - category: 文件分类（可选），如 'avatar', 'product', 'document' 等，用于组织存储目录
        - filename: 自定义文件名（可选），用于指定文件名（包括扩展名）。如果不提供，将自动生成 UUID
    
    返回:
        {
            "code": 200,
            "message": "上传成功",
            "data": {
                "filename": "原始文件名",
                "url": "https://static.zhongrongxinfu.cn/uploads/xxxx.jpg",
                "path": "/uploads/xxxx.jpg",
                "size": 12345,
                "type": "image",
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
            filename=my-product.jpg
    """
    # 获取上传的文件
    if 'file' not in request.files:
        return jsonify({"code": 400, "message": "请选择要上传的文件"}), 400
    
    file = request.files['file']
    category = request.form.get('category', 'uploads')  # 默认分类为 uploads
    custom_filename = request.form.get('filename')  # 可选的自定义文件名
    
    base_dir = os.path.expanduser(UPLOAD_FILE_DIR)
    success, result = _save_file_to_path(file, None, base_dir, category, use_filename=custom_filename)
    
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
        - filenames: JSON 数组，对应每个文件的自定义文件名（可选）
          格式: ["file1.jpg", "file2.png", "file3.jpg"] 或 "{\"0\": \"file1.jpg\", \"1\": \"file2.png\"}"
    
    返回:
        {
            "code": 200,
            "message": "批量上传完成",
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
            filenames=["product1.jpg", "product2.png", "product3.jpg"]
    """
    if 'files' not in request.files:
        return jsonify({"code": 400, "message": "请选择要上传的文件"}), 400
    
    files = request.files.getlist('files')
    category = request.form.get('category', 'uploads')
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
        
        success, result = _save_file_to_path(file, None, base_dir, category, use_filename=custom_filename)
        
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
