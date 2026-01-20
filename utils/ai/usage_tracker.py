"""
AI使用统计追踪工具
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.mysql import connect


class AIUsageTracker:
    """AI使用统计追踪器"""
    
    @staticmethod
    def log_usage(
        user_id: str,
        conversation_id: Optional[str],
        model_key: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        input_cost: float,
        output_cost: float,
        total_cost: float,
        cache_hit_tokens: int = 0,
        cache_miss_tokens: int = 0,
        cache_hit_cost: float = 0
    ) -> bool:
        """
        记录AI使用日志
        
        Args:
            user_id: 用户ID
            conversation_id: 会话ID
            model_key: 模型标识
            provider: 提供商
            input_tokens: 输入tokens
            output_tokens: 输出tokens
            total_tokens: 总tokens
            input_cost: 输入费用
            output_cost: 输出费用
            total_cost: 总费用
            cache_hit_tokens: 缓存命中tokens
            cache_miss_tokens: 缓存未命中tokens
            cache_hit_cost: 缓存命中费用
            
        Returns:
            bool: 是否成功
        """
        try:
            connection = connect()
            sql = """
                INSERT INTO ai_usage_log (
                    user_id, conversation_id, model_key, provider,
                    input_tokens, output_tokens, total_tokens,
                    cache_hit_tokens, cache_miss_tokens,
                    input_cost, output_cost, cache_hit_cost, total_cost
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                user_id, conversation_id, model_key, provider,
                input_tokens, output_tokens, total_tokens,
                cache_hit_tokens, cache_miss_tokens,
                input_cost, output_cost, cache_hit_cost, total_cost
            )
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"记录AI使用日志失败: {e}")
            return False
    
    @staticmethod
    def get_user_usage_stats(
        user_id: str,
        time_range: str = '1h',
        model_key: Optional[str] = None
    ) -> Dict:
        """
        获取用户使用统计
        
        Args:
            user_id: 用户ID
            time_range: 时间范围 (1h, 1d, 1w, 1y)
            model_key: 模型标识（可选，不传则查询所有模型）
            
        Returns:
            Dict: 统计数据
        """
        # 计算时间范围
        now = datetime.now()
        time_ranges = {
            '1h': now - timedelta(hours=1),
            '1d': now - timedelta(days=1),
            '1w': now - timedelta(weeks=1),
            '1y': now - timedelta(days=365)
        }
        
        start_time = time_ranges.get(time_range, time_ranges['1d'])
        
        # 构建SQL查询
        base_sql = """
            SELECT 
                model_key,
                provider,
                COUNT(*) as request_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cache_hit_tokens) as total_cache_hit_tokens,
                SUM(cache_miss_tokens) as total_cache_miss_tokens,
                SUM(input_cost) as total_input_cost,
                SUM(output_cost) as total_output_cost,
                SUM(cache_hit_cost) as total_cache_hit_cost,
                SUM(total_cost) as total_cost
            FROM ai_usage_log
            WHERE user_id = %s AND created_at >= %s
        """
        
        params = [user_id, start_time]
        
        if model_key:
            base_sql += " AND model_key = %s"
            params.append(model_key)
        
        base_sql += " GROUP BY model_key, provider"
        
        try:
            connection = connect()
            results = None
            with connection.cursor() as cursor:
                cursor.execute(base_sql, tuple(params))
                results = cursor.fetchall()
            connection.close()
            
            # 格式化返回数据
            stats = {
                'time_range': time_range,
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                'models': []
            }
            
            total_requests = 0
            total_tokens_all = 0
            total_cost_all = 0.0
            
            for row in results:
                model_stat = {
                    'model_key': row['model_key'],
                    'provider': row['provider'],
                    'request_count': row['request_count'],
                    'tokens': {
                        'input': int(row['total_input_tokens'] or 0),
                        'output': int(row['total_output_tokens'] or 0),
                        'total': int(row['total_tokens'] or 0),
                        'cache_hit': int(row['total_cache_hit_tokens'] or 0),
                        'cache_miss': int(row['total_cache_miss_tokens'] or 0)
                    },
                    'cost': {
                        'input': float(row['total_input_cost'] or 0),
                        'output': float(row['total_output_cost'] or 0),
                        'cache_hit': float(row['total_cache_hit_cost'] or 0),
                        'total': float(row['total_cost'] or 0)
                    }
                }
                stats['models'].append(model_stat)
                
                total_requests += model_stat['request_count']
                total_tokens_all += model_stat['tokens']['total']
                total_cost_all += model_stat['cost']['total']
            
            stats['summary'] = {
                'total_requests': total_requests,
                'total_tokens': total_tokens_all,
                'total_cost': round(total_cost_all, 6)
            }
            
            return stats
            
        except Exception as e:
            print(f"获取用户使用统计失败: {e}")
            return {
                'error': str(e),
                'time_range': time_range,
                'models': []
            }
    
    @staticmethod
    def get_user_usage_history(
        user_id: str,
        time_range: str = '1d',
        limit: int = 100
    ) -> List[Dict]:
        """
        获取用户使用历史记录
        
        Args:
            user_id: 用户ID
            time_range: 时间范围
            limit: 返回记录数限制
            
        Returns:
            List[Dict]: 历史记录列表
        """
        now = datetime.now()
        time_ranges = {
            '1h': now - timedelta(hours=1),
            '1d': now - timedelta(days=1),
            '1w': now - timedelta(weeks=1),
            '1y': now - timedelta(days=365)
        }
        
        start_time = time_ranges.get(time_range, time_ranges['1d'])
        
        sql = """
            SELECT 
                id, conversation_id, model_key, provider,
                input_tokens, output_tokens, total_tokens,
                cache_hit_tokens, cache_miss_tokens,
                input_cost, output_cost, cache_hit_cost, total_cost,
                created_at
            FROM ai_usage_log
            WHERE user_id = %s AND created_at >= %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        try:
            connection = connect()
            results = None
            with connection.cursor() as cursor:
                cursor.execute(sql, (user_id, start_time, limit))
                results = cursor.fetchall()
            connection.close()
            
            history = []
            for row in results:
                record = {
                    'id': row['id'],
                    'conversation_id': row['conversation_id'],
                    'model_key': row['model_key'],
                    'provider': row['provider'],
                    'tokens': {
                        'input': int(row['input_tokens']),
                        'output': int(row['output_tokens']),
                        'total': int(row['total_tokens']),
                        'cache_hit': int(row['cache_hit_tokens'] or 0),
                        'cache_miss': int(row['cache_miss_tokens'] or 0)
                    },
                    'cost': {
                        'input': float(row['input_cost']),
                        'output': float(row['output_cost']),
                        'cache_hit': float(row['cache_hit_cost'] or 0),
                        'total': float(row['total_cost'])
                    },
                    'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                }
                history.append(record)
            
            return history
            
        except Exception as e:
            print(f"获取用户使用历史失败: {e}")
            return []
    
    @staticmethod
    def get_model_config(model_key: str) -> Optional[Dict]:
        """
        获取模型配置信息
        
        Args:
            model_key: 模型标识
            
        Returns:
            Optional[Dict]: 模型配置
        """
        sql = """
            SELECT 
                id, model_key, model_name, provider,
                input_price, output_price, cache_hit_price,
                input_threshold, output_threshold, is_active
            FROM ai_model_config
            WHERE model_key = %s AND is_active = 1
        """
        
        try:
            connection = connect()
            results = None
            with connection.cursor() as cursor:
                cursor.execute(sql, (model_key,))
                results = cursor.fetchall()
            connection.close()
            
            if results:
                row = results[0]
                return {
                    'id': row['id'],
                    'model_key': row['model_key'],
                    'model_name': row['model_name'],
                    'provider': row['provider'],
                    'input_price': float(row['input_price']),
                    'output_price': float(row['output_price']),
                    'cache_hit_price': float(row['cache_hit_price']) if row['cache_hit_price'] else None,
                    'input_threshold': row['input_threshold'],
                    'output_threshold': row['output_threshold'],
                    'is_active': row['is_active']
                }
            return None
        except Exception as e:
            print(f"获取模型配置失败: {e}")
            return None
    
    @staticmethod
    def add_model_config(
        model_key: str,
        model_name: str,
        provider: str,
        input_price: float,
        output_price: float,
        cache_hit_price: Optional[float] = None,
        input_threshold: Optional[int] = None,
        output_threshold: Optional[int] = None
    ) -> bool:
        """
        添加新的模型配置
        
        Args:
            model_key: 模型标识
            model_name: 模型名称
            provider: 提供商
            input_price: 输入价格（元/百万tokens）
            output_price: 输出价格（元/百万tokens）
            cache_hit_price: 缓存命中价格
            input_threshold: 输入分段阈值
            output_threshold: 输出分段阈值
            
        Returns:
            bool: 是否成功
        """
        sql = """
            INSERT INTO ai_model_config (
                model_key, model_name, provider,
                input_price, output_price, cache_hit_price,
                input_threshold, output_threshold
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                model_name = VALUES(model_name),
                input_price = VALUES(input_price),
                output_price = VALUES(output_price),
                cache_hit_price = VALUES(cache_hit_price),
                input_threshold = VALUES(input_threshold),
                output_threshold = VALUES(output_threshold),
                updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            connection = connect()
            with connection.cursor() as cursor:
                cursor.execute(sql, (
                    model_key, model_name, provider,
                    input_price, output_price, cache_hit_price,
                    input_threshold, output_threshold
                ))
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"添加模型配置失败: {e}")
            return False
    
    @staticmethod
    def get_platform_model_stats(
        time_range: str = '1d',
        model_key: Optional[str] = None
    ) -> Dict:
        """
        获取全平台模型使用统计（管理员功能）
        
        Args:
            time_range: 时间范围 (1h, 1d, 1w, 1y, all)
            model_key: 模型标识（可选，不传则查询所有模型）
            
        Returns:
            Dict: 统计数据，包含每个模型的用户数、请求数、token和费用
        """
        # 计算时间范围
        if time_range != 'all':
            now = datetime.now()
            time_ranges = {
                '1h': now - timedelta(hours=1),
                '1d': now - timedelta(days=1),
                '1w': now - timedelta(weeks=1),
                '1y': now - timedelta(days=365)
            }
            start_time = time_ranges.get(time_range, time_ranges['1d'])
        else:
            start_time = None
        
        # 构建SQL查询
        base_sql = """
            SELECT 
                model_key,
                provider,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(*) as request_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cache_hit_tokens) as total_cache_hit_tokens,
                SUM(cache_miss_tokens) as total_cache_miss_tokens,
                SUM(input_cost) as total_input_cost,
                SUM(output_cost) as total_output_cost,
                SUM(cache_hit_cost) as total_cache_hit_cost,
                SUM(total_cost) as total_cost,
                MIN(created_at) as first_usage,
                MAX(created_at) as last_usage
            FROM ai_usage_log
            WHERE 1=1
        """
        
        params = []
        
        if start_time:
            base_sql += " AND created_at >= %s"
            params.append(start_time)
        
        if model_key:
            base_sql += " AND model_key = %s"
            params.append(model_key)
        
        base_sql += " GROUP BY model_key, provider ORDER BY total_cost DESC"
        
        try:
            connection = connect()
            results = None
            with connection.cursor() as cursor:
                cursor.execute(base_sql, tuple(params))
                results = cursor.fetchall()
            connection.close()
            
            # 格式化返回数据
            stats = {
                'time_range': time_range,
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'all time',
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'models': []
            }
            
            total_users = set()
            total_requests = 0
            total_tokens_all = 0
            total_cost_all = 0.0
            
            for row in results:
                model_stat = {
                    'model_key': row['model_key'],
                    'provider': row['provider'],
                    'unique_users': row['unique_users'],
                    'request_count': row['request_count'],
                    'total_tokens': int(row['total_tokens'] or 0),
                    'tokens': {
                        'input': int(row['total_input_tokens'] or 0),
                        'output': int(row['total_output_tokens'] or 0),
                        'total': int(row['total_tokens'] or 0),
                        'cache_hit': int(row['total_cache_hit_tokens'] or 0),
                        'cache_miss': int(row['total_cache_miss_tokens'] or 0)
                    },
                    'cost': {},
                    'usage_period': {
                        'first_usage': row['first_usage'].strftime('%Y-%m-%d %H:%M:%S') if row['first_usage'] else None,
                        'last_usage': row['last_usage'].strftime('%Y-%m-%d %H:%M:%S') if row['last_usage'] else None
                    }
                }

                # 补充成本相关字段
                model_stat['cost']['input'] = float(row['total_input_cost'] or 0)
                model_stat['cost']['output'] = float(row['total_output_cost'] or 0)
                model_stat['cost']['cache_hit'] = float(row['total_cache_hit_cost'] or 0)
                model_stat['cost']['total'] = float(row['total_cost'] or 0)
                model_stat['cost']['per_request'] = (
                    model_stat['cost']['total'] / model_stat['request_count']
                    if model_stat['request_count'] else 0
                )

                # 缓存命中率
                total_tokens = model_stat['tokens']['total']
                cache_hit_tokens = model_stat['tokens']['cache_hit']
                model_stat['cache_hit_rate'] = (
                    cache_hit_tokens / total_tokens if total_tokens else 0
                )
                stats['models'].append(model_stat)
                
                total_requests += model_stat['request_count']
                total_tokens_all += model_stat['tokens']['total']
                total_cost_all += model_stat['cost']['total']
            
            # 获取总用户数（跨模型去重）
            if results:
                user_count_sql = """
                    SELECT COUNT(DISTINCT user_id) as unique_users
                    FROM ai_usage_log
                    WHERE 1=1
                """
                user_params = []
                if start_time:
                    user_count_sql += " AND created_at >= %s"
                    user_params.append(start_time)
                if model_key:
                    user_count_sql += " AND model_key = %s"
                    user_params.append(model_key)
                
                conn = connect()
                with conn.cursor() as cursor:
                    cursor.execute(user_count_sql, tuple(user_params))
                    user_result = cursor.fetchall()
                conn.close()
                
                total_unique_users = user_result[0]['unique_users'] if user_result else 0
            else:
                total_unique_users = 0
            
            stats['summary'] = {
                'total_unique_users': total_unique_users,
                'total_requests': total_requests,
                'total_tokens': int(total_tokens_all),
                'total_cost': round(total_cost_all, 6),
                'avg_cost_per_request': round(total_cost_all / total_requests, 6) if total_requests > 0 else 0,
                'avg_tokens_per_request': round(total_tokens_all / total_requests, 2) if total_requests > 0 else 0
            }
            
            return stats
            
        except Exception as e:
            print(f"获取平台模型统计失败: {e}")
            return {
                'error': str(e),
                'time_range': time_range,
                'models': []
            }

    @staticmethod
    def get_time_series_stats(
        time_range: str = '1d',
        model_key: Optional[str] = None
    ) -> Dict:
        """
        获取时间序列使用统计
        Args:
            time_range: 时间范围 (1h, 1d, 1w, 1y, all)
            model_key: 模型标识（可选）
        Returns:
            Dict: 时间序列统计结果
        """
        now = datetime.now()
        bucket_map = {
            '1h': {
                'start': now - timedelta(hours=1),
                'bucket': "DATE_FORMAT(FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(created_at)/600)*600), '%%Y-%%m-%%d %%H:%%i')",
                'label': '10m'
            },
            '1d': {
                'start': now - timedelta(days=1),
                'bucket': "DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:00:00')",
                'label': '1h'
            },
            '1w': {
                'start': now - timedelta(weeks=1),
                'bucket': "DATE_FORMAT(created_at, '%%Y-%%m-%%d')",
                'label': '1d'
            },
            '1y': {
                'start': now - timedelta(days=365),
                'bucket': "DATE_FORMAT(DATE_SUB(created_at, INTERVAL WEEKDAY(created_at) DAY), '%%Y-%%m-%%d')",
                'label': '1w'
            },
            'all': {
                'start': None,
                'bucket': "DATE_FORMAT(created_at, '%%Y-%%m-01')",
                'label': '1M'
            }
        }

        config = bucket_map.get(time_range, bucket_map['1d'])
        start_time = config['start']
        bucket_expr = config['bucket']

        sql = f"""
            SELECT
                {bucket_expr} AS bucket,
                SUM(input_tokens) AS input_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(cache_hit_tokens) AS cache_hit_tokens,
                COUNT(*) AS request_count
            FROM ai_usage_log
            WHERE 1=1
        """

        params = []
        if start_time:
            sql += " AND created_at >= %s"
            params.append(start_time)
        if model_key:
            sql += " AND model_key = %s"
            params.append(model_key)

        sql += " GROUP BY bucket ORDER BY bucket ASC"

        try:
            connection = connect()
            results = None
            with connection.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                results = cursor.fetchall()
            connection.close()

            time_series = []
            summary = {
                'total_requests': 0,
                'total_tokens': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0
            }

            for row in results:
                total_tokens = int(row['total_tokens'] or 0)
                input_tokens = int(row['input_tokens'] or 0)
                output_tokens = int(row['output_tokens'] or 0)
                request_count = row['request_count'] or 0
                cache_hit_tokens = int(row['cache_hit_tokens'] or 0)

                entry = {
                    'date': row['bucket'],
                    'total_tokens': total_tokens,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'request_count': request_count,
                    'cache_hit': cache_hit_tokens > 0
                }

                if cache_hit_tokens > 0:
                    entry['cache_info'] = {
                        'input_cached': cache_hit_tokens,
                        'output_cached': 0
                    }

                time_series.append(entry)

                summary['total_requests'] += request_count
                summary['total_tokens'] += total_tokens
                summary['total_input_tokens'] += input_tokens
                summary['total_output_tokens'] += output_tokens

            return {
                'time_range': time_range,
                'bucket': config['label'],
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'all time',
                'end_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                'time_series': time_series,
                'summary': summary
            }
        except Exception as e:
            print(f"获取时间序列统计失败: {e}")
            return {
                'error': str(e),
                'time_range': time_range,
                'time_series': [],
                'summary': {}
            }
    
    @staticmethod
    def get_user_ranking(
        time_range: str = '1d',
        model_key: Optional[str] = None,
        order_by: str = 'cost',
        limit: int = 50
    ) -> List[Dict]:
        """
        获取用户使用排行榜（管理员功能）
        
        Args:
            time_range: 时间范围 (1h, 1d, 1w, 1y, all)
            model_key: 模型标识（可选）
            order_by: 排序字段 (cost, tokens, requests)
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 用户排行列表
        """
        # 计算时间范围
        if time_range != 'all':
            now = datetime.now()
            time_ranges = {
                '1h': now - timedelta(hours=1),
                '1d': now - timedelta(days=1),
                '1w': now - timedelta(weeks=1),
                '1y': now - timedelta(days=365)
            }
            start_time = time_ranges.get(time_range, time_ranges['1d'])
        else:
            start_time = None
        
        # 确定排序字段
        order_map = {
            'cost': 'total_cost DESC',
            'tokens': 'total_tokens DESC',
            'requests': 'request_count DESC'
        }
        order_clause = order_map.get(order_by, 'total_cost DESC')
        
        # 构建SQL查询
        base_sql = """
            SELECT 
                user_id,
                COUNT(*) as request_count,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost) as total_cost,
                MIN(created_at) as first_usage,
                MAX(created_at) as last_usage
            FROM ai_usage_log
            WHERE 1=1
        """
        
        params = []
        
        if start_time:
            base_sql += " AND created_at >= %s"
            params.append(start_time)
        
        if model_key:
            base_sql += " AND model_key = %s"
            params.append(model_key)
        
        base_sql += f" GROUP BY user_id ORDER BY {order_clause} LIMIT %s"
        params.append(limit)
        
        try:
            connection = connect()
            results = None
            with connection.cursor() as cursor:
                cursor.execute(base_sql, tuple(params))
                results = cursor.fetchall()
            connection.close()
            
            ranking = []
            for idx, row in enumerate(results, 1):
                request_count = row['request_count'] or 0
                total_cost = float(row['total_cost'] or 0)
                avg_cost = total_cost / request_count if request_count > 0 else 0
                
                user_stat = {
                    'rank': idx,
                    'user_id': row['user_id'],
                    'request_count': row['request_count'],
                    'total_tokens': int(row['total_tokens'] or 0),
                    'total_cost': total_cost,
                    'avg_cost_per_request': avg_cost,
                    'last_usage_time': row['last_usage'].strftime('%Y-%m-%d %H:%M:%S') if row['last_usage'] else None,
                    'usage_period': {
                        'first_usage': row['first_usage'].strftime('%Y-%m-%d %H:%M:%S') if row['first_usage'] else None,
                        'last_usage': row['last_usage'].strftime('%Y-%m-%d %H:%M:%S') if row['last_usage'] else None
                    }
                }
                ranking.append(user_stat)
            
            return ranking
            
        except Exception as e:
            print(f"获取用户排行失败: {e}")
            return []
