-- 对话历史表
CREATE TABLE IF NOT EXISTS `conversations` (
  `id` VARCHAR(36) PRIMARY KEY COMMENT '对话ID (UUID)',
  `user_id` VARCHAR(36) NOT NULL COMMENT '用户ID',
  `model` VARCHAR(50) NOT NULL COMMENT '模型名称 (deepseek/doubao)',
  `title` VARCHAR(255) DEFAULT '新对话' COMMENT '对话标题',
  `messages` JSON NOT NULL COMMENT '对话消息历史 (JSON数组)',
  `files` JSON DEFAULT NULL COMMENT '上传的文件路径列表',
  `analysis_type` VARCHAR(20) DEFAULT NULL COMMENT '分析类型 (personal/company)，普通对话为NULL',
  `file_details` JSON DEFAULT NULL COMMENT '文件详情列表 (包含文件名、大小、上传时间等)',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_model` (`model`),
  INDEX `idx_created_at` (`created_at`),
  INDEX `idx_analysis_type` (`analysis_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI对话历史表';

-- 如果表已存在，添加新字段（兼容已有数据库）
ALTER TABLE `conversations` 
  ADD COLUMN IF NOT EXISTS `analysis_type` VARCHAR(20) DEFAULT NULL COMMENT '分析类型 (personal/company)，普通对话为NULL' AFTER `files`,
  ADD COLUMN IF NOT EXISTS `file_details` JSON DEFAULT NULL COMMENT '文件详情列表 (包含文件名、大小、上传时间等)' AFTER `analysis_type`,
  ADD INDEX IF NOT EXISTS `idx_analysis_type` (`analysis_type`);


-- 继续改进这个项目，提供deepseek与doubao两个模型的支持，两种模型都需要支持单文件上传（包括单文件多次上传）、多文件上传、连续对话记忆等功能