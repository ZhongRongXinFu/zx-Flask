import sys, uuid, os, pymysql
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import PRODUCT_IMAGE_DIR
from datetime import datetime
from flask import Flask, Blueprint, Response, stream_with_context, request, jsonify, g
from utils.mysql import connect
from utils.login import login_required, op_required

product_page = Blueprint('product', __name__)

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
        "name": "name"
    }
    if sort_by not in allowed_sort_fields:
        sort_by = "updated_at"
    if order not in ("asc", "desc"):
        order = "desc"

    offset = (page - 1) * range_size

    # 不同平台的列和基础过滤
    base_where = []
    columns_miniprogram = "id, uuid, name, logo, tag, slogan, price, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features"
    columns_manager = "id, uuid, name, logo, tag, slogan, price, is_online, manager, department, description, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features, created_at, updated_at"

    if f == "miniprogram":
        base_where.append("is_online = 1")
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
    name = request.form.get("name")
    tag = request.form.get("tag")
    slogan = request.form.get("slogan")
    price = request.form.get("price")
    is_online = request.form.get("is_online")
    manager = request.form.get("manager", None)
    department = request.form.get("department", None)
    description = request.form.get("description", None)
    bank_name = request.form.get("bank_name", "暂无")
    reference_rate = request.form.get("reference_rate", "暂无")
    loan_amount = request.form.get("loan_amount", "暂无")
    loan_term = request.form.get("loan_term", "暂无")
    repayment_method = request.form.get("repayment_method", "暂无")
    guarantee_method = request.form.get("guarantee_method", "暂无")
    approval_mode = request.form.get("approval_mode", "暂无")
    usage_target = request.form.get("usage_target", "暂无")
    organization = request.form.get("organization", "暂无")
    service_area = request.form.get("service_area", "暂无")
    product_features = request.form.get("product_features", "暂无")
    logo = request.form.get("logo")

    if not logo or not name or not tag or not slogan or not price or not is_online:
        return jsonify({"code": 400, "message": "缺少必要字段"})
    
    product_uuid = str(uuid.uuid4())

    connection = connect()
    try:
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO product
                (name, tag, slogan, price, is_online, manager, department, description, logo, uuid, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql, (name, tag, slogan, price, is_online, manager, department, description, logo, product_uuid, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features))
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
    product_uuid = request.form.get("uuid")
    name = request.form.get("name")
    tag = request.form.get("tag")
    slogan = request.form.get("slogan")
    price = request.form.get("price")
    is_online = request.form.get("is_online")
    manager = request.form.get("manager", None)
    department = request.form.get("department", None)
    description = request.form.get("description", None)
    bank_name = request.form.get("bank_name", None)
    reference_rate = request.form.get("reference_rate", None)
    loan_amount = request.form.get("loan_amount", None)
    loan_term = request.form.get("loan_term", None)
    repayment_method = request.form.get("repayment_method", None)
    guarantee_method = request.form.get("guarantee_method", None)
    approval_mode = request.form.get("approval_mode", None)
    usage_target = request.form.get("usage_target", None)
    organization = request.form.get("organization", None)
    service_area = request.form.get("service_area", None)
    product_features = request.form.get("product_features", None)
    logo = request.form.get("logo")

    # print("request.form:", request.form)

    if not product_uuid or not logo or not name or not tag or not slogan or not price or not is_online:
        print(product_uuid, logo, name, tag, slogan, price, is_online)
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
            cursor.execute(sql, (name, tag, slogan, price, is_online, manager, department, description, logo, bank_name, reference_rate, loan_amount, loan_term, repayment_method, guarantee_method, approval_mode, usage_target, organization, service_area, product_features, product_uuid))
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
        return jsonify({ "code": 200, "message": "删除成功" })
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
            sql = """
                UPDATE product SET
                detail_html=%s
                WHERE uuid=%s
            """
            cursor.execute(sql, (data, product_uuid))
            rows = cursor.fetchall()
        connection.commit()
        return jsonify({ "code": 200, "data": rows }), 200
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