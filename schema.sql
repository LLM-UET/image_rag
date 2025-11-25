-- ============================================================================
-- Telco Customer Service - MySQL Database Schema
-- Compatible with MySQL 5.7+ (requires JSON column support)
-- ============================================================================

-- Create database
CREATE DATABASE IF NOT EXISTS telco_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE telco_db;

-- ============================================================================
-- 1. SYSTEM ADMINISTRATION TABLES
-- ============================================================================

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL COMMENT 'Hashed password',
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL COMMENT 'e.g., Admin, Telco Operator',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL COMMENT 'e.g., view_financial_data, edit_faq',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Employee-Role junction table (M-to-N)
CREATE TABLE IF NOT EXISTS employee_roles (
    employee_id INT NOT NULL,
    role_id INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (employee_id, role_id),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Role-Permission junction table (M-to-N)
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INT NOT NULL,
    permission_id INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 2. KNOWLEDGE BASE TABLES
-- ============================================================================

-- FAQs table
CREATE TABLE IF NOT EXISTS faqs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FULLTEXT KEY ft_question_answer (question, answer)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Packages table (Telecom plans)
CREATE TABLE IF NOT EXISTS packages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL COMMENT 'Package code e.g., SD70, V120',
    metadata JSON COMMENT 'Dynamic fields: price, data_limit, voice_minutes, etc.',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Package metadata interpretation
CREATE TABLE IF NOT EXISTS package_metadata_interpretations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    field_name VARCHAR(100) UNIQUE NOT NULL COMMENT 'JSON key e.g., data_limit',
    field_local_name VARCHAR(255) COMMENT 'Vietnamese name e.g., Lưu lượng data',
    field_interpretation TEXT COMMENT 'Semantic description for AI reasoning',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_field_name (field_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 3. CUSTOMER & CS OPERATIONS TABLES
-- ============================================================================

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    status ENUM('inactive', 'active', 'suspended', 'cancelled') DEFAULT 'active',
    balance DECIMAL(15,2) DEFAULT 0.00 COMMENT 'Account balance in VND',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone (phone_number),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Customer-Package subscriptions (M-to-N)
CREATE TABLE IF NOT EXISTS customer_packages (
    customer_id INT NOT NULL,
    package_id INT NOT NULL,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL COMMENT 'Subscription expiry',
    status ENUM('active', 'expired', 'cancelled') DEFAULT 'active',
    PRIMARY KEY (customer_id, package_id),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (package_id) REFERENCES packages(id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- CS Chat sessions
CREATE TABLE IF NOT EXISTS cs_chats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    type ENUM('TEXT', 'AUDIO') NOT NULL COMMENT 'Livechat or Voice Call',
    summary TEXT COMMENT 'AI-generated conversation summary',
    customer_satisfaction ENUM('UNKNOWN', 'EXCELLENT', 'GOOD', 'NEUTRAL', 'BAD', 'TERRIBLE') DEFAULT 'UNKNOWN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    INDEX idx_customer_id (customer_id),
    INDEX idx_type (type),
    INDEX idx_satisfaction (customer_satisfaction),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- CS Chat messages
CREATE TABLE IF NOT EXISTS cs_chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cs_chat_id INT NOT NULL,
    text_content TEXT NOT NULL COMMENT 'Message text or STT transcript',
    emotion VARCHAR(50) COMMENT 'AI-detected emotion for this message',
    sender ENUM('EMPLOYEE', 'CUSTOMER') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cs_chat_id) REFERENCES cs_chats(id) ON DELETE CASCADE,
    INDEX idx_cs_chat_id (cs_chat_id),
    INDEX idx_sender (sender),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================

-- Insert sample permissions
INSERT IGNORE INTO permissions (name, description) VALUES
    ('view_financial_data', 'View customer balance and transactions'),
    ('edit_faq', 'Create and modify FAQ entries'),
    ('manage_packages', 'Create and modify telecom packages'),
    ('view_chats', 'View customer service chat history'),
    ('manage_employees', 'Manage employee accounts');

-- Insert sample roles
INSERT IGNORE INTO roles (name, description) VALUES
    ('Admin', 'Full system access'),
    ('Telco Operator', 'Customer service agent'),
    ('Manager', 'Supervisory access');

-- Link roles to permissions (Admin gets all)
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id 
FROM roles r, permissions p 
WHERE r.name = 'Admin';

-- Insert sample package metadata interpretations
INSERT IGNORE INTO package_metadata_interpretations (field_name, field_local_name, field_interpretation) VALUES
    ('price', 'Giá gói cước', 'Monthly subscription fee in Vietnamese Dong (VND)'),
    ('data_limit', 'Lưu lượng data', 'Amount of high-speed 4G/5G data included in the package'),
    ('data_unit', 'Đơn vị data', 'Unit of data measurement (GB/day, GB/month, MB/day, etc.)'),
    ('voice_minutes', 'Phút gọi', 'Number of voice call minutes included, or "unlimited" for unlimited calls'),
    ('validity_days', 'Chu kỳ', 'Package validity period in days (30 = monthly, 365 = yearly)'),
    ('sms_count', 'Tin nhắn SMS', 'Number of SMS messages included in the package'),
    ('special_features', 'Tính năng đặc biệt', 'Additional features like free internal calls, bonus data, etc.'),
    ('description', 'Mô tả', 'Brief description of the package benefits');

-- Insert sample packages
INSERT IGNORE INTO packages (name, metadata) VALUES
    ('SD70', JSON_OBJECT(
        'price', '70000',
        'data_limit', '3',
        'data_unit', 'GB/day',
        'voice_minutes', 'unlimited',
        'validity_days', '30',
        'sms_count', '50',
        'description', 'Gói data 3GB/ngày tốc độ cao'
    )),
    ('V120', JSON_OBJECT(
        'price', '120000',
        'data_limit', '4',
        'data_unit', 'GB/day',
        'voice_minutes', 'unlimited',
        'validity_days', '30',
        'sms_count', '100',
        'description', 'Gói data 4GB/ngày + gọi thoại không giới hạn'
    )),
    ('MAX200', JSON_OBJECT(
        'price', '200000',
        'data_limit', '6',
        'data_unit', 'GB/day',
        'voice_minutes', 'unlimited',
        'validity_days', '30',
        'sms_count', '200',
        'special_features', 'Miễn phí gọi nội mạng, data tốc độ cao',
        'description', 'Gói cao cấp 6GB/ngày + nhiều ưu đãi'
    ));

-- ============================================================================
-- USEFUL QUERIES FOR PACKAGE METADATA
-- ============================================================================

-- Query packages with price < 100,000 VND
-- SELECT * FROM packages 
-- WHERE CAST(JSON_EXTRACT(metadata, '$.price') AS UNSIGNED) < 100000;

-- Query packages with unlimited voice
-- SELECT * FROM packages 
-- WHERE JSON_EXTRACT(metadata, '$.voice_minutes') = 'unlimited';

-- Query packages by data limit
-- SELECT name, JSON_EXTRACT(metadata, '$.data_limit') as data_gb
-- FROM packages 
-- WHERE CAST(JSON_EXTRACT(metadata, '$.data_limit') AS UNSIGNED) >= 4;

-- Get all package metadata keys (distinct)
-- SELECT DISTINCT JSON_KEYS(metadata) FROM packages;

-- ============================================================================
-- INDEXES & PERFORMANCE
-- ============================================================================

-- Add generated column for price (for better query performance)
-- ALTER TABLE packages 
-- ADD COLUMN price_vnd INT GENERATED ALWAYS AS (CAST(JSON_EXTRACT(metadata, '$.price') AS UNSIGNED)) STORED,
-- ADD INDEX idx_price (price_vnd);

-- ============================================================================
-- COMPLETED
-- ============================================================================
SELECT 'Database schema created successfully!' AS status;
