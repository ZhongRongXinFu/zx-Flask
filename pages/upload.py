import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import time
import shutil
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from settings import UPLOAD_FILE_DIR
from utils.login import login_required, op_required
from utils.ai.pdfmaker import submit_convert, query_task, OFFICE_EXTS
from utils.mysql import connect

upload_page = Blueprint('upload', __name__)


def _check_login_for_category(category: str):
    """
    为特定 category 检查登录状态
    仅在 category != 'avatar' 时需要登录
    
    成功时返回 (True, None)
    失败时返回 (False, error_response)
    """
    if category == 'avatar':
        # avatar 可以不登录
        return True, None
    
    # 其他分类需要验证 token
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
    if not token:
        token = request.headers.get('X-Token')
    
    if not token:
        return False, jsonify({"code": 401, "message": "请先登录"}), 401
    
    conn = connect()
    try:
        with conn.cursor() as cursor:
            # 先删除过期的 token
            cursor.execute("""
                DELETE FROM user_token
                WHERE token = %s AND expire_at <= %s
            """, (token, datetime.now(timezone.utc)))
            
            # 查询有效的 token 和用户信息
            cursor.execute("""
                SELECT u.*
                FROM user_token t
                JOIN user u ON t.uuid = u.uuid
                WHERE t.token = %s AND t.expire_at > %s
            """, (token, datetime.now(timezone.utc)))
            user = cursor.fetchone()
            
            if not user:
                return False, jsonify({"code": 401, "message": "登录已过期，请重新登录"}), 401
            
            # 存到 g 里，后续接口直接用 g.current_user
            g.current_user = user
            conn.commit()
            return True, None
    except Exception as e:
        return False, jsonify({"code": 500, "message": f"登录验证失败: {str(e)}"}), 500
    finally:
        conn.close()

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    # 图片
    'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'},
    # 文档
    'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md', 'csv'}
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
        
        convert_error = None

        if category == "ai-chat" and f".{ext}" in OFFICE_EXTS:
            # 先保存原始文件到临时位置
            temp_file_path = absolute_path
            file.save(temp_file_path)

            try:
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
                    print("PDF转换超时")
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
            except Exception as convert_exc:
                convert_error = f"PDF转换失败，已保留原文件: {convert_exc}"
                # 保留原始文件，不再删除
                is_converted = False
        else:
            # 保存文件
            file.save(absolute_path)
        
        # 获取文件大小
        file_size = os.path.getsize(absolute_path)
        
        # 构建公网 URL
        url_path = relative_path.replace('\\', '/')
        
        if category in ['avatar', 'product_icon', 'richtext', 'swiper', 'title']:
            t = "?t=" + str(int(time.time()))
        else:
            t = ""

        public_url = f"https://static.zhongrongxinfu.cn/{url_path}{t}"
        
        return True, {
            "filename": original_filename if not is_converted else original_filename.rsplit('.', 1)[0] + '.pdf',
            "url": public_url,
            "path": f"/{url_path}",
            "size": file_size,
            "type": file_type,
            "converted": is_converted,
            "convert_error": convert_error,
            "uploaded_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"文件保存失败: {str(e)}")
        # 如果保存失败，尝试删除已创建的文件
        if os.path.exists(absolute_path):
            try:
                os.remove(absolute_path)
            except:
                pass
        
        return False, f"文件保存失败: {str(e)}"


@upload_page.route("/", methods=["POST"])
def upload_file():
    """
    统一文件上传接口
    
    参数:
        - file: 要上传的文件（通过 multipart/form-data）
        - category: 文件分类（可选），如 'avatar', 'product', 'document', 'ai-chat' 等，用于组织存储目录
        - subcategory: 二级分类（可选），用于在 category 下创建子目录
        - filename: 自定义文件名（可选），不包含扩展名，扩展名使用原始文件的扩展名
    
    权限说明:
        - category=avatar 时可以不登录上传
        - 其他 category 需要登录
    
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
        
        5. 不登录上传头像:
            POST /upload/
            file=<图片文件>
            category=avatar
            filename=user-avatar
            # 无需登录即可上传
    """
    # 获取上传的文件
    if 'file' not in request.files:
        return jsonify({"code": 400, "message": "请选择要上传的文件"}), 400
    
    file = request.files['file']
    category = request.form.get('category', 'uploads')  # 默认分类为 uploads
    
    # 检查登录状态（avatar 分类可以不登录）
    login_ok, login_error = _check_login_for_category(category)
    if not login_ok:
        return login_error
    
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


@upload_page.route("/delete/", methods=["DELETE"])
@login_required
def delete_file():
    """
    删除文件或目录接口
    
    权限说明：
        - 管理员（is_op=1）：可以删除任何路径下的文件或目录
        - 普通用户：只能删除以下路径：
            1. /ai-chat/<用户uuid>/ 下的所有文件和子目录
            2. /avatar/<用户uuid>.jpg/png/gif等图片格式
    
    请求参数：
        - path: 要删除的文件或目录路径（相对于上传基目录）
                例如: "ai-chat/12345678-1234-1234-1234-123456789abc"
                      "avatar/user-123.jpg"
    
    返回：
        删除成功：
        {
            "code": 0,
            "message": "删除成功",
            "data": {
                "path": "ai-chat/user-uuid",
                "deleted_type": "directory",  # 或 "file"
                "deleted_items": 5  # 如果是目录，显示删除的文件数
            }
        }
        
        权限不足：
        {
            "code": 403,
            "message": "权限不足，无法删除该路径"
        }
        
        文件不存在：
        {
            "code": 404,
            "message": "文件或目录不存在"
        }
    """
    user_id = g.current_user["uuid"]
    is_admin = str(g.current_user.get("is_op", "0")) == "1"
    
    def _normalize_delete_path(raw_path: str):
        """清洗前端传入的路径，兼容域名、uploads 前缀、查询参数等。"""
        if not raw_path:
            return None

        # 去掉查询参数
        path_no_query = raw_path.split("?", 1)[0].strip()

        # 去掉可能出现的域名前缀
        for prefix in (
            "https://api.zhongrongxinfu.cn/",
            "http://api.zhongrongxinfu.cn/",
            "https://static.zhongrongxinfu.cn/",
            "http://static.zhongrongxinfu.cn/",
        ):
            if path_no_query.startswith(prefix):
                path_no_query = path_no_query[len(prefix):]
                break

        # 去掉开头的斜杠
        while path_no_query.startswith('/'):
            path_no_query = path_no_query[1:]

        # 去掉 uploads/ 前缀（公网 URL 会包含 uploads/）
        if path_no_query.startswith("uploads/"):
            path_no_query = path_no_query[len("uploads/"):]

        # 标准化为无首尾斜杠的相对路径
        return path_no_query.strip('/')

    # 获取要删除的路径
    raw_path = request.json.get("path") if request.is_json else request.form.get("path")
    path = _normalize_delete_path(raw_path)

    if not path:
        return jsonify({"code": 400, "message": "请提供要删除的路径"}), 400

    # 防止路径遍历攻击
    if '..' in path or path.startswith('/'):
        return jsonify({"code": 400, "message": "非法的路径"}), 400
    
    base_dir = os.path.expanduser(UPLOAD_FILE_DIR)
    full_path = os.path.join(base_dir, path)
    
    # 确保解析后的路径仍在基目录内
    real_full_path = os.path.realpath(full_path)
    real_base_dir = os.path.realpath(base_dir)
    if not real_full_path.startswith(real_base_dir):
        return jsonify({"code": 403, "message": "权限不足，无法删除该路径"}), 403
    
    # 权限检查（非管理员）
    if not is_admin:
        # 检查是否是允许的路径
        allowed = False
        
        # 检查 ai-chat/<用户uuid>/ 路径
        if path.startswith(f"ai-chat/{user_id}"):
            allowed = True
        
        # 检查 avatar/<用户uuid>.<图片扩展名> 路径
        elif path.startswith(f"avatar/{user_id}."):
            # 获取文件扩展名
            _, ext = os.path.splitext(path)
            if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico']:
                allowed = True
        
        if not allowed:
            return jsonify({"code": 403, "message": "权限不足，无法删除该路径"}), 403
    
    # 检查文件/目录是否存在
    if not os.path.exists(full_path):
        return jsonify({"code": 404, "message": "文件或目录不存在"}), 404
    
    try:
        deleted_type = None
        deleted_items = 0
        
        if os.path.isfile(full_path):
            # 删除单个文件
            os.remove(full_path)
            deleted_type = "file"
            deleted_items = 1
        elif os.path.isdir(full_path):
            # 删除目录及其所有内容
            deleted_items = _count_items_recursive(full_path)
            shutil.rmtree(full_path)
            deleted_type = "directory"
        
        return jsonify({
            "code": 0,
            "message": "删除成功",
            "data": {
                "path": path,
                "deleted_type": deleted_type,
                "deleted_items": deleted_items
            }
        }), 200
    
    except Exception as e:
        print(f"删除文件失败: {str(e)}")
        return jsonify({"code": 500, "message": f"删除失败: {str(e)}"}), 500


def _count_items_recursive(directory):
    """递归计算目录中的文件数（包括子目录中的文件）"""
    count = 0
    try:
        for root, dirs, files in os.walk(directory):
            count += len(files)
    except:
        pass
    return count
