"""
AI额度变动日志工具
"""
import pymysql
from utils.mysql import connect


def log_quota_change(
    user_id: int,
    uuid: str,
    change_type: str,
    change_amount: int,
    quota_before: int,
    quota_after: int,
    related_id: str = None,
    remark: str = None
) -> bool:
    """
    记录AI额度变动日志
    
    Args:
        user_id: 用户ID
        uuid: 用户UUID
        change_type: 变动类型 (redeem/consume/refund/admin/purchase)
        change_amount: 变动额度（正数为增加，负数为减少）
        quota_before: 变动前额度
        quota_after: 变动后额度
        related_id: 关联ID（兑换码/会话ID/订单号等）
        remark: 备注说明
    
    Returns:
        bool: 是否记录成功
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO ai_quota_log 
                (user_id, uuid, change_type, change_amount, quota_before, quota_after, related_id, remark)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                user_id,
                uuid,
                change_type,
                change_amount,
                quota_before,
                quota_after,
                related_id,
                remark
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"记录额度变动日志失败: {e}")
        return False
    finally:
        conn.close()


def get_quota_logs(
    uuid: str = None,
    change_type: str = None,
    limit: int = 100,
    offset: int = 0
):
    """
    查询额度变动日志
    
    Args:
        uuid: 用户UUID（可选）
        change_type: 变动类型（可选）
        limit: 返回记录数
        offset: 偏移量
    
    Returns:
        list: 日志记录列表
    """
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建查询条件
            where_clauses = []
            params = []
            
            if uuid:
                where_clauses.append("uuid = %s")
                params.append(uuid)
            
            if change_type:
                where_clauses.append("change_type = %s")
                params.append(change_type)
            
            where_sql = ""
            if where_clauses:
                where_sql = " WHERE " + " AND ".join(where_clauses)
            
            # 查询总数
            count_sql = f"SELECT COUNT(*) as total FROM ai_quota_log{where_sql}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["total"]
            
            # 查询数据
            sql = f"""
                SELECT 
                    id, user_id, uuid, change_type, change_amount,
                    quota_before, quota_after, related_id, remark, created_at
                FROM ai_quota_log{where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            return {
                "total": total,
                "data": results
            }
    finally:
        conn.close()
