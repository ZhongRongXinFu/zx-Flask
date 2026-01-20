-- AI使用统计数据库表结构

-- 1. AI模型配置表（存储不同模型的价格信息）
CREATE TABLE IF NOT EXISTS `ai_model_config` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `model_key` VARCHAR(100) NOT NULL UNIQUE COMMENT '模型唯一标识，如：deepseek-chat, doubao-seed-1-8-251228',
  `model_name` VARCHAR(100) NOT NULL COMMENT '模型显示名称',
  `provider` VARCHAR(50) NOT NULL COMMENT '提供商：deepseek, doubao',
  `input_price` DECIMAL(10, 6) NOT NULL COMMENT '输入价格（元/百万tokens）',
  `output_price` DECIMAL(10, 6) NOT NULL COMMENT '输出价格（元/百万tokens）',
  `cache_hit_price` DECIMAL(10, 6) DEFAULT NULL COMMENT '缓存命中价格（元/百万tokens）',
  `input_threshold` INT DEFAULT NULL COMMENT '输入分段阈值（tokens）',
  `output_threshold` INT DEFAULT NULL COMMENT '输出分段阈值（tokens）',
  `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `idx_provider` (`provider`),
  INDEX `idx_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI模型配置表';

-- 插入默认模型配置
INSERT INTO `ai_model_config` (`model_key`, `model_name`, `provider`, `input_price`, `output_price`, `cache_hit_price`, `input_threshold`, `output_threshold`) VALUES
('deepseek-chat', 'DeepSeek Chat', 'deepseek', 2.0, 3.0, 0.2, NULL, NULL),
('doubao-seed-1-8-251228', '豆包 Seed 1.8', 'doubao', 0.8, 2.0, 0.16, 32768, 200);

-- 2. AI使用记录表（存储每次调用的详细信息）
CREATE TABLE IF NOT EXISTS `ai_usage_log` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(36) NOT NULL COMMENT '用户UUID',
  `conversation_id` VARCHAR(36) DEFAULT NULL COMMENT '会话ID',
  `model_key` VARCHAR(100) NOT NULL COMMENT '模型标识',
  `provider` VARCHAR(50) NOT NULL COMMENT '提供商',
  
  -- Token统计
  `input_tokens` INT NOT NULL DEFAULT 0 COMMENT '输入tokens总数',
  `output_tokens` INT NOT NULL DEFAULT 0 COMMENT '输出tokens总数',
  `total_tokens` INT NOT NULL DEFAULT 0 COMMENT 'tokens总数',
  
  -- 缓存相关
  `cache_hit_tokens` INT DEFAULT 0 COMMENT '缓存命中tokens',
  `cache_miss_tokens` INT DEFAULT 0 COMMENT '缓存未命中tokens',
  
  -- 费用统计
  `input_cost` DECIMAL(10, 6) NOT NULL DEFAULT 0 COMMENT '输入费用（元）',
  `output_cost` DECIMAL(10, 6) NOT NULL DEFAULT 0 COMMENT '输出费用（元）',
  `cache_hit_cost` DECIMAL(10, 6) DEFAULT 0 COMMENT '缓存命中费用（元）',
  `total_cost` DECIMAL(10, 6) NOT NULL DEFAULT 0 COMMENT '总费用（元）',
  
  -- 时间戳
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_conversation_id` (`conversation_id`),
  INDEX `idx_model_key` (`model_key`),
  INDEX `idx_provider` (`provider`),
  INDEX `idx_created_at` (`created_at`),
  INDEX `idx_user_created` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI使用记录表';

-- 3. 用户使用统计汇总表（可选，用于快速查询）
CREATE TABLE IF NOT EXISTS `ai_usage_summary` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `user_id` VARCHAR(36) NOT NULL COMMENT '用户UUID',
  `model_key` VARCHAR(100) NOT NULL COMMENT '模型标识',
  `date` DATE NOT NULL COMMENT '统计日期',
  
  -- 统计数据
  `total_requests` INT NOT NULL DEFAULT 0 COMMENT '请求次数',
  `total_input_tokens` BIGINT NOT NULL DEFAULT 0 COMMENT '总输入tokens',
  `total_output_tokens` BIGINT NOT NULL DEFAULT 0 COMMENT '总输出tokens',
  `total_tokens` BIGINT NOT NULL DEFAULT 0 COMMENT '总tokens',
  `total_cost` DECIMAL(10, 2) NOT NULL DEFAULT 0 COMMENT '总费用（元）',
  
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  UNIQUE KEY `uk_user_model_date` (`user_id`, `model_key`, `date`),
  INDEX `idx_date` (`date`),
  INDEX `idx_user_date` (`user_id`, `date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI使用统计汇总表';
