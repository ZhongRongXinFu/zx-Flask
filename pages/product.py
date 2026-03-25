import re
import shutil
import sys, uuid, os, pymysql
from pathlib import Path
from urllib.parse import unquote, urlsplit
sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import MEDIA_FILE_DIR, MEDIA_BASE_URL, PRODUCT_IMAGE_DIR
from datetime import datetime
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify, g
from utils.mysql import connect
from utils.login import login_required, op_required

product_page = Blueprint('product', __name__)
HOME_VISIBLE_DEFAULT = 1

RICH_TEXT_MEDIA_CATEGORIES = ("product-media", "richtext")
RICH_TEXT_MEDIA_URL_RE = re.compile(
    rf"""(?P<url>(?:https?://{re.escape(urlsplit(MEDIA_BASE_URL).netloc)}|/)(?:product-media|richtext)/[^"'<>)\[\]\s]+)""",
    re.IGNORECASE,
)


def _normalize_flag(value, *, default=None, field_name="flag"):
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int):
        if value in (0, 1):
            return value
        raise ValueError(f"{field_name} must be 0 or 1")

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("0", "1"):
            return int(normalized)
        if normalized in ("true", "false"):
            return 1 if normalized == "true" else 0

    raise ValueError(f"{field_name} must be 0 or 1")


def _extract_rich_text_media_paths(html: str):
    if not html:
        return set()

    paths = set()
    for match in RICH_TEXT_MEDIA_URL_RE.finditer(html):
        candidate = match.group("url")
        parsed = urlsplit(candidate)
        path = unquote(parsed.path or "").lstrip("/")
        if not path:
            continue

        segments = path.split("/")
        if len(segments) < 2:
            continue
        if segments[0] not in RICH_TEXT_MEDIA_CATEGORIES:
            continue

        paths.add("/".join(segments))

    return paths


def _safe_media_absolute_path(relative_path: str):
    media_root = os.path.realpath(os.path.expanduser(MEDIA_FILE_DIR))
    absolute_path = os.path.realpath(os.path.join(media_root, relative_path))
    if not absolute_path.startswith(media_root):
        return None, media_root
    return absolute_path, media_root


def _prune_empty_media_dirs(start_path: str, stop_path: str):
    current = os.path.dirname(start_path)
    stop_path = os.path.realpath(stop_path)
    while current.startswith(stop_path) and current != stop_path:
        try:
            if os.listdir(current):
                break
            os.rmdir(current)
        except OSError:
            break
        current = os.path.dirname(current)


def _delete_rich_text_media_paths(paths):
    deleted = []
    missing = []
    skipped = []
    failed = []

    for relative_path in sorted(paths):
        absolute_path, media_root = _safe_media_absolute_path(relative_path)
        if not absolute_path:
            skipped.append(relative_path)
            continue

        if not os.path.exists(absolute_path):
            missing.append(relative_path)
            continue

        try:
            os.remove(absolute_path)
            _prune_empty_media_dirs(absolute_path, media_root)
            deleted.append(relative_path)
        except Exception as exc:
            failed.append({"path": relative_path, "error": str(exc)})

    return {
        "deleted": deleted,
        "missing": missing,
        "skipped": skipped,
        "failed": failed,
    }


def _delete_product_rich_text_media_tree(product_uuid: str):
    deleted = []
    missing = []
    failed = []

    for category in RICH_TEXT_MEDIA_CATEGORIES:
        relative_dir = os.path.join(category, product_uuid)
        absolute_dir, media_root = _safe_media_absolute_path(relative_dir)
        if not absolute_dir:
            failed.append({"path": relative_dir.replace("\\", "/"), "error": "invalid path"})
            continue

        if not os.path.exists(absolute_dir):
            missing.append(relative_dir.replace("\\", "/"))
            continue

        try:
            shutil.rmtree(absolute_dir)
            _prune_empty_media_dirs(absolute_dir, media_root)
            deleted.append(relative_dir.replace("\\", "/"))
        except Exception as exc:
            failed.append({"path": relative_dir.replace("\\", "/"), "error": str(exc)})

    return {
        "deleted_dirs": deleted,
        "missing_dirs": missing,
        "failed": failed,
    }

@product_page.route("/list/<f>/", methods=["GET", "POST"])
def get_list(f):
    # 分页参数
    page = request.args.get("page", 1, type=int)
    range_size = request.args.get("range", 10, type=int)

    # 排序参数
    sort_by = request.args.get("sort_by", "updated_at", type=str)
    order = request.args.get("order", "desc", type=str).lower()

    # 过滤参数
    name = request.args.get("name", type=str)
    tag = request.args.get("tag", type=str)
    manager = request.args.get("manager", type=str)
    department = request.args.get("department", type=str)
    is_online_filter = request.args.get("is_online", type=int)
    is_home_visible_filter = request.args.get("is_home_visible", type=int)
    price = request.args.get("price", type=float)
    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    created_start = request.args.get("created_start", type=str)
    created_end = request.args.get("created_end", type=str)
    updated_start = request.args.get("updated_start", type=str)
    updated_end = request.args.get("updated_end", type=str)

    if page < 1:
        return jsonify({"code": 400, "message": "page 必须大于等于1"}), 400
    if range_size < 1 or range_size > 500:
        return jsonify({"code": 400, "message": "range 必须在1-500之间"}), 400

    allowed_sort_fields = {
        "updated_at": "updated_at",
        "created_at": "created_at",
        "price": "price",
        "is_online": "is_online",
        "is_home_visible": "is_home_visible",
        "name": "name"
    }
    if sort_by not in allowed_sort_fields:
        sort_by = "updated_at"
    if order not in ("asc", "desc"):
        order = "desc"

    offset = (page - 1) * range_size

    # 不同平台的列和基础过滤
    base_where = []
    columns_miniprogram = "id, uuid, name, logo, tag, slogan, price, is_online, is_home_visible, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features"
    columns_manager = "id, uuid, name, logo, tag, slogan, price, is_online, is_home_visible, manager, department, description, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features, created_at, updated_at"

    if f == "miniprogram":
        base_where.append("is_online = 1")
        base_where.append("is_home_visible = 1")
        select_columns = columns_miniprogram
    elif f == "manager-component":
        base_where.append("is_online = 1")
        select_columns = columns_manager
    elif f == "manager":
        select_columns = columns_manager
    else:
        return jsonify({"code": 400, "message": "不支持的平台类型"}), 400

    where_clauses = list(base_where)
    params = []

    if name:
        where_clauses.append("name LIKE %s")
        params.append(f"%{name}%")
    if tag:
        where_clauses.append("tag LIKE %s")
        params.append(f"%{tag}%")
    if manager:
        where_clauses.append("manager LIKE %s")
        params.append(f"%{manager}%")
    if department:
        where_clauses.append("department LIKE %s")
        params.append(f"%{department}%")
    if is_online_filter in (0, 1):
        where_clauses.append("is_online = %s")
        params.append(is_online_filter)
    if f == "manager" and is_home_visible_filter in (0, 1):
        where_clauses.append("is_home_visible = %s")
        params.append(is_home_visible_filter)

    if price is not None:
        where_clauses.append("price = %s")
        params.append(price)
    else:
        if price_min is not None:
            where_clauses.append("price >= %s")
            params.append(price_min)
        if price_max is not None:
            where_clauses.append("price <= %s")
            params.append(price_max)

    if created_start:
        where_clauses.append("created_at >= %s")
        params.append(created_start)
    if created_end:
        where_clauses.append("created_at <= %s")
        params.append(created_end)
    if updated_start:
        where_clauses.append("updated_at >= %s")
        params.append(updated_start)
    if updated_end:
        where_clauses.append("updated_at <= %s")
        params.append(updated_end)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    connection = connect()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            count_sql = f"SELECT COUNT(*) as total FROM `product`{where_sql}"
            cursor.execute(count_sql, params)
            total_result = cursor.fetchone()
            total = total_result.get("total", 0) if total_result else 0

            select_sql = (
                f"SELECT {select_columns} "
                "FROM `product`"
                f"{where_sql} "
                f"ORDER BY {allowed_sort_fields[sort_by]} {order.upper()} "
                "LIMIT %s OFFSET %s"
            )
            exec_params = list(params)
            exec_params.extend([range_size, offset])
            cursor.execute(select_sql, exec_params)
            rows = cursor.fetchall()
            for row in rows:
                if isinstance(row.get("created_at"), datetime):
                    row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(row.get("updated_at"), datetime):
                    row["updated_at"] = row["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return jsonify({"code": 400, "message": f"查询失败: {str(e)}"}), 400
    finally:
        connection.close()

    total_pages = (total + range_size - 1) // range_size

    return jsonify({
        "code": 200,
        "data": rows,
        "pagination": {
            "page": page,
            "range": range_size,
            "total": total,
            "total_pages": total_pages
        }
    })

@product_page.route("/new/", methods=["GET", "POST"])
@login_required
@op_required
def create_product():
    data = request.get_json() or {}
    name = data.get("name")
    tag = data.get("tag")
    slogan = data.get("slogan")
    price = data.get("price")
    try:
        is_online = _normalize_flag(data.get("is_online"), field_name="is_online")
        is_home_visible = _normalize_flag(
            data.get("is_home_visible"),
            default=HOME_VISIBLE_DEFAULT,
            field_name="is_home_visible",
        )
    except ValueError as exc:
        return jsonify({"code": 400, "message": str(exc)})
    manager = data.get("manager")
    department = data.get("department")
    description = data.get("description")
    bank_name = data.get("bank_name", "暂无")
    reference_rate = data.get("reference_rate", "暂无")
    loan_amount = data.get("loan_amount", "暂无")
    loan_term = data.get("loan_term", "暂无")
    repayment_method = data.get("repayment_method", "暂无")
    guarantee_method = data.get("guarantee_method", "暂无")
    approval_mode = data.get("approval_mode", "暂无")
    usage_target = data.get("usage_target", "暂无")
    organization = data.get("organization", "暂无")
    service_area = data.get("service_area", "暂无")
    product_features = data.get("product_features", "暂无")
    logo = data.get("logo")

    if not logo or not name or not tag or not slogan or not price or is_online is None:
        return jsonify({"code": 400, "message": "缺少必要字段"})
    
    product_uuid = str(uuid.uuid4())

    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO product
                (name, tag, slogan, price, is_online, is_home_visible, manager, department, description, logo, uuid, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql, (name, tag, slogan, price, is_online, is_home_visible, manager, department, description, logo, product_uuid, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features))
            rows = cursor.fetchall()
        connection.commit()
        return jsonify({ "code": 200, "data": rows })
    except Exception as e:
        return jsonify({ "code": 400, "message": f"新建失败: {str(e)}" })
    finally:
        connection.close()

@product_page.route("/update/", methods=["GET", "POST"])
@login_required
@op_required
def update_product():
    data = request.get_json() or {}
    product_uuid = data.get("uuid")
    name = data.get("name")
    tag = data.get("tag")
    slogan = data.get("slogan")
    price = data.get("price")
    try:
        is_online = _normalize_flag(data.get("is_online"), field_name="is_online")
        is_home_visible = _normalize_flag(
            data.get("is_home_visible"),
            default=HOME_VISIBLE_DEFAULT,
            field_name="is_home_visible",
        )
    except ValueError as exc:
        return jsonify({"code": 400, "message": str(exc)})
    manager = data.get("manager")
    department = data.get("department")
    description = data.get("description")
    bank_name = data.get("bank_name")
    reference_rate = data.get("reference_rate")
    loan_amount = data.get("loan_amount")
    loan_term = data.get("loan_term")
    repayment_method = data.get("repayment_method")
    guarantee_method = data.get("guarantee_method")
    approval_mode = data.get("approval_mode")
    usage_target = data.get("usage_target")
    organization = data.get("organization")
    service_area = data.get("service_area")
    product_features = data.get("product_features")
    logo = data.get("logo")

    # print("request.form:", request.form)

    if not product_uuid or not logo or not name or not tag or not slogan or not price or is_online is None:
        # print(product_uuid, logo, name, tag, slogan, price, is_online)
        return jsonify({"code": 400, "message": "缺少必要字段"})
    
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM product WHERE uuid=%s", (product_uuid,))
            product = cursor.fetchone()
        if not product:
            connection.close()
            return jsonify({"code": 404, "message": "商品不存在"})
    except Exception as e:
        connection.close()
        return jsonify({"code": 500, "message": f"数据库查询错误: {e}"})

    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = """
                UPDATE product SET
                name=%s,
                tag=%s,
                slogan=%s,
                price=%s,
                is_online=%s,
                is_home_visible=%s,
                manager=%s,
                department=%s,
                description=%s,
                logo=%s,
                bank_name=%s,
                reference_rate=%s,
                loan_amount=%s,
                loan_term=%s,
                repayment_method=%s,
                guarantee_method=%s,
                approval_mode=%s,
                usage_target=%s,
                organization=%s,
                service_area=%s,
                product_features=%s
                WHERE uuid=%s
            """
            cursor.execute(sql, (name, tag, slogan, price, is_online, is_home_visible, manager, department, description, logo, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features, product_uuid))
            rows = cursor.fetchall()
        connection.commit()
        return jsonify({ "code": 200, "data": rows })
    except Exception as e:
        return jsonify({ "code": 400, "message": f"编辑失败: {str(e)}" })
    finally:
        connection.close()

@product_page.route("/info/<product_uuid>/", methods=["GET", "POST"])
def info_product(product_uuid):
    r = request.args.get("rich_text", "false")
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = f"""SELECT 
                id,
                uuid,
                name,
                logo,
                tag,
                slogan,
                price,
                is_online,
                is_home_visible,
                manager,
                department,
                description,
                bank_name,
                reference_rate,
                loan_amount,
                loan_term,
                repayment_method,
                guarantee_method,
                approval_mode,
                usage_target,
                organization,
                service_area,
                product_features,
                created_at,
                updated_at
                {', detail_html ' if r.lower() == 'true' else ''}
            FROM `product` WHERE uuid = %s"""
            cursor.execute(sql, (product_uuid,))
            row = cursor.fetchone()
            if not row:
                return jsonify({ "code": 404, "message": "商品不存在" })
        return jsonify({ "code": 200, "data": row })
    except Exception as e:
        return jsonify({ "code": 400, "message": f"查询失败: {str(e)}" })
    finally:
        connection.close()

@product_page.route("/delete/<product_uuid>/", methods=["DELETE"])
@login_required
@op_required
def delete_product(product_uuid):
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = "DELETE FROM product WHERE uuid = %s"
            cursor.execute(sql, (product_uuid,))
        connection.commit()
        cleanup = _delete_product_rich_text_media_tree(product_uuid)
        return jsonify({ "code": 200, "message": "删除成功", "cleanup": cleanup })
    except Exception as e:
        return jsonify({ "code": 400, "message": f"删除失败: {str(e)}" })
    finally:
        connection.close() 

@product_page.route("/rich-text/edit/", methods=["POST"])
@login_required
@op_required
def edit_product_rich_text():
    data = request.form.get("data")
    product_uuid = request.form.get("uuid")
    if not data or not product_uuid:
        return jsonify({"code": 400, "message": "缺少必要字段"}), 400
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT detail_html FROM product WHERE uuid=%s", (product_uuid,))
            product = cursor.fetchone()
            if not product:
                return jsonify({"code": 404, "message": "商品不存在"}), 404

            previous_html = product.get("detail_html") if isinstance(product, dict) else product[0]
            sql = """
                UPDATE product SET
                detail_html=%s
                WHERE uuid=%s
            """
            cursor.execute(sql, (data, product_uuid))
            rows = cursor.fetchall()
        connection.commit()
        old_paths = _extract_rich_text_media_paths(previous_html)
        new_paths = _extract_rich_text_media_paths(data)
        cleanup = _delete_rich_text_media_paths(old_paths - new_paths)
        cleanup["kept"] = sorted(new_paths)
        cleanup["removed_count"] = len(cleanup["deleted"])
        return jsonify({ "code": 200, "data": rows, "cleanup": cleanup }), 200
    except Exception as e:
        return jsonify({ "code": 400, "message": f"编辑失败: {str(e)}" }), 400
    finally:
        connection.close()

@product_page.route("/rich-text/get/", methods=["GET"])
def get_product_rich_text():
    product_uuid = request.args.get("uuid")
    if not product_uuid:
        return jsonify({"code": 400, "message": "缺少必要字段"}), 400
    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT detail_html FROM product WHERE uuid=%s
            """
            cursor.execute(sql, (product_uuid,))
            row = cursor.fetchone()
        if not row:
            return jsonify({"code": 404, "message": "商品不存在"}), 404
        return jsonify({ "code": 200, "data": row }), 200
    except Exception as e:
        return jsonify({ "code": 400, "message": f"查询失败: {str(e)}" }), 400
    finally:
        connection.close()
