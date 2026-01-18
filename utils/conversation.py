"""
AI对话数据库操作模块
支持对话历史的增删改查，包括分析会话的特殊字段处理
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
import json
from datetime import datetime
from utils.mysql import connect


def create_conversation(user_id: str, model: str, title: str = "新对话", analysis_type: str = None) -> dict:
    """
    创建新对话会话
    
    Args:
        user_id: 用户ID
        model: 模型名称 (deepseek/doubao)
        title: 对话标题
        analysis_type: 分析类型 (personal/company)，普通对话时为None
    
    Returns:
        dict: 创建的对话对象，包含id, user_id, model, title, messages等字段
    """
    conversation_id = str(uuid.uuid4())
    messages = []
    files = []
    file_details = []
    created_at = datetime.now()
    
    conn = connect()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO conversations 
                (id, user_id, model, title, messages, files, analysis_type, file_details, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                conversation_id,
                user_id,
                model,
                title,
                json.dumps(messages, ensure_ascii=False),
                json.dumps(files, ensure_ascii=False),
                analysis_type,  # 可以为None
                json.dumps(file_details, ensure_ascii=False),
                created_at,
                created_at
            ))
        conn.commit()
        
        return {
            "id": conversation_id,
            "user_id": user_id,
            "model": model,
            "title": title,
            "messages": messages,
            "files": files,
            "analysis_type": analysis_type,
            "file_details": file_details,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat()
        }
    finally:
        conn.close()


def get_conversation(conversation_id: str, user_id: str = None) -> dict:
    """
    获取对话详情
    
    Args:
        conversation_id: 对话ID
        user_id: 用户ID（可选，用于权限验证）
    
    Returns:
        dict: 对话对象，如果不存在或无权限则返回None
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            if user_id:
                sql = "SELECT * FROM conversations WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (conversation_id, user_id))
            else:
                sql = "SELECT * FROM conversations WHERE id = %s"
                cursor.execute(sql, (conversation_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # 解析JSON字段
            conversation = dict(row)
            
            # 安全解析messages
            try:
                conversation["messages"] = json.loads(row["messages"]) if row["messages"] else []
            except (json.JSONDecodeError, TypeError):
                conversation["messages"] = []
            
            # 安全解析files
            try:
                conversation["files"] = json.loads(row["files"]) if row["files"] else []
            except (json.JSONDecodeError, TypeError):
                conversation["files"] = []
            
            # 安全解析file_details
            try:
                conversation["file_details"] = json.loads(row["file_details"]) if row.get("file_details") else []
            except (json.JSONDecodeError, TypeError):
                conversation["file_details"] = []
            
            # 处理analysis_type字段（可能不存在或为NULL）
            conversation["analysis_type"] = row.get("analysis_type")
            
            # 格式化时间
            if "created_at" in conversation and conversation["created_at"]:
                conversation["created_at"] = conversation["created_at"].isoformat() if hasattr(conversation["created_at"], "isoformat") else str(conversation["created_at"])
            if "updated_at" in conversation and conversation["updated_at"]:
                conversation["updated_at"] = conversation["updated_at"].isoformat() if hasattr(conversation["updated_at"], "isoformat") else str(conversation["updated_at"])
            
            return conversation
    finally:
        conn.close()


def update_conversation(conversation_id: str, messages: list, files: list = None, 
                       title: str = None, file_details: list = None) -> bool:
    """
    更新对话内容
    
    Args:
        conversation_id: 对话ID
        messages: 消息列表
        files: 文件路径列表（可选）
        title: 对话标题（可选）
        file_details: 文件详情列表（可选，用于分析会话）
    
    Returns:
        bool: 是否更新成功
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            # 构建动态SQL
            update_fields = ["messages = %s", "updated_at = %s"]
            params = [json.dumps(messages, ensure_ascii=False), datetime.now()]
            
            if files is not None:
                update_fields.append("files = %s")
                params.append(json.dumps(files, ensure_ascii=False))
            
            if title is not None:
                update_fields.append("title = %s")
                params.append(title)
            
            if file_details is not None:
                update_fields.append("file_details = %s")
                params.append(json.dumps(file_details, ensure_ascii=False))
            
            params.append(conversation_id)
            
            sql = f"UPDATE conversations SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(sql, params)
        
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_conversations(user_id: str, model: str = None, limit: int = 50, offset: int = 0, 
                      analysis_type: str = None) -> list:
    """
    获取用户的对话列表
    
    Args:
        user_id: 用户ID
        model: 模型名称筛选（可选，deepseek/doubao）
        limit: 返回数量限制
        offset: 偏移量
        analysis_type: 筛选分析类型（None=全部, "none"=普通对话, "personal"/"company"=分析会话）
    
    Returns:
        list: 对话列表，按更新时间倒序排列
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            # 构建WHERE条件
            where_conditions = ["user_id = %s"]
            params = [user_id]
            
            # 添加模型筛选
            if model:
                where_conditions.append("model = %s")
                params.append(model)
            
            # 添加分析类型筛选
            if analysis_type == "none":
                where_conditions.append("(analysis_type IS NULL OR analysis_type = '')")
            elif analysis_type:
                where_conditions.append("analysis_type = %s")
                params.append(analysis_type)
            
            # 组合SQL
            where_clause = " AND ".join(where_conditions)
            sql = f"""
                SELECT id, user_id, model, title, created_at, updated_at, analysis_type
                FROM conversations 
                WHERE {where_clause}
                ORDER BY updated_at DESC 
                LIMIT %s OFFSET %s
            """
            
            params.extend([limit, offset])
            cursor.execute(sql, params)
            
            rows = cursor.fetchall()
            conversations = []
            
            for row in rows:
                conv = dict(row)
                # 格式化时间
                if "created_at" in conv and conv["created_at"]:
                    conv["created_at"] = conv["created_at"].isoformat() if hasattr(conv["created_at"], "isoformat") else str(conv["created_at"])
                if "updated_at" in conv and conv["updated_at"]:
                    conv["updated_at"] = conv["updated_at"].isoformat() if hasattr(conv["updated_at"], "isoformat") else str(conv["updated_at"])
                
                conversations.append(conv)
            
            return conversations
    finally:
        conn.close()


def delete_conversation(conversation_id: str, user_id: str = None) -> bool:
    """
    删除对话
    
    Args:
        conversation_id: 对话ID
        user_id: 用户ID（可选，用于权限验证）
    
    Returns:
        bool: 是否删除成功
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            if user_id:
                sql = "DELETE FROM conversations WHERE id = %s AND user_id = %s"
                cursor.execute(sql, (conversation_id, user_id))
            else:
                sql = "DELETE FROM conversations WHERE id = %s"
                cursor.execute(sql, (conversation_id,))
        
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_all_conversations(user_id: str) -> int:
    """
    删除用户的所有对话
    
    Args:
        user_id: 用户ID
    
    Returns:
        int: 删除的对话数量
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM conversations WHERE user_id = %s"
            cursor.execute(sql, (user_id,))
        
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_conversation_count(user_id: str, model: str = None, analysis_type: str = None) -> int:
    """
    获取用户的对话数量
    
    Args:
        user_id: 用户ID
        model: 模型名称筛选（可选，deepseek/doubao）
        analysis_type: 筛选分析类型（None=全部, "none"=普通对话, "personal"/"company"=分析会话）
    
    Returns:
        int: 对话数量
    """
    conn = connect()
    try:
        with conn.cursor() as cursor:
            # 构建WHERE条件
            where_conditions = ["user_id = %s"]
            params = [user_id]
            
            # 添加模型筛选
            if model:
                where_conditions.append("model = %s")
                params.append(model)
            
            # 添加分析类型筛选
            if analysis_type == "none":
                where_conditions.append("(analysis_type IS NULL OR analysis_type = '')")
            elif analysis_type:
                where_conditions.append("analysis_type = %s")
                params.append(analysis_type)
            
            # 组合SQL
            where_clause = " AND ".join(where_conditions)
            sql = f"SELECT COUNT(*) as count FROM conversations WHERE {where_clause}"
            cursor.execute(sql, params)
            
            result = cursor.fetchone()
            return result["count"] if result else 0
    finally:
        conn.close()


if __name__ == "__main__":
    # 测试代码
    print("=== 测试 conversation.py ===")
    
    # 创建普通对话
    test_user_id = "test-user-123"
    conv1 = create_conversation(test_user_id, "deepseek", "测试普通对话")
    print(f"✓ 创建普通对话: {conv1['id']}")
    
    # 创建分析会话
    conv2 = create_conversation(test_user_id, "deepseek", "测试个人分析", analysis_type="personal")
    print(f"✓ 创建个人分析会话: {conv2['id']}")
    
    conv3 = create_conversation(test_user_id, "deepseek", "测试企业分析", analysis_type="company")
    print(f"✓ 创建企业分析会话: {conv3['id']}")
    
    # 更新对话
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
    ]
    update_conversation(conv1['id'], messages, title="更新后的标题")
    print(f"✓ 更新对话: {conv1['id']}")
    
    # 更新分析会话（带file_details）
    file_details = [
        {"filename": "test.pdf", "size": 1024, "uploaded_at": datetime.now().isoformat()}
    ]
    update_conversation(conv2['id'], messages, file_details=file_details)
    print(f"✓ 更新分析会话: {conv2['id']}")
    
    # 获取对话
    retrieved = get_conversation(conv1['id'], test_user_id)
    print(f"✓ 获取对话: {retrieved['title']}")
    
    # 列出对话
    all_convs = list_conversations(test_user_id)
    print(f"✓ 列出所有对话: {len(all_convs)} 个")
    
    normal_convs = list_conversations(test_user_id, analysis_type="none")
    print(f"✓ 列出普通对话: {len(normal_convs)} 个")
    
    personal_convs = list_conversations(test_user_id, analysis_type="personal")
    print(f"✓ 列出个人分析会话: {len(personal_convs)} 个")
    
    # 统计数量
    total_count = get_conversation_count(test_user_id)
    print(f"✓ 对话总数: {total_count}")
    
    # 删除对话
    delete_conversation(conv1['id'], test_user_id)
    print(f"✓ 删除对话: {conv1['id']}")
    
    # 批量删除
    deleted_count = delete_all_conversations(test_user_id)
    print(f"✓ 批量删除: {deleted_count} 个对话")
    
    print("\n=== 测试完成 ===")
