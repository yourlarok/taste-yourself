-- Fit analysis data. Measurements are centimetres unless noted otherwise.
CREATE TABLE user_fit_profiles (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL UNIQUE,
  height_cm DECIMAL(5,1) NULL,
  weight_kg DECIMAL(5,1) NULL,
  chest_cm DECIMAL(5,1) NULL,
  waist_cm DECIMAL(5,1) NULL,
  hip_cm DECIMAL(5,1) NULL,
  fit_preference VARCHAR(16) NOT NULL DEFAULT 'regular',
  measurement_source VARCHAR(32) NOT NULL DEFAULT 'manual',
  measurement_confidence DECIMAL(4,3) NULL,
  consented_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_fit_data (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  external_product_id VARCHAR(128) NOT NULL,
  external_sku_id VARCHAR(128) NOT NULL UNIQUE,
  brand VARCHAR(128) NULL,
  category VARCHAR(32) NOT NULL,
  size_label VARCHAR(32) NOT NULL,
  stretch_percent DECIMAL(5,2) NOT NULL DEFAULT 0,
  measurements_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_product (external_product_id, size_label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fit_analysis_logs (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  analysis_id CHAR(36) NOT NULL UNIQUE,
  user_id BIGINT UNSIGNED NOT NULL,
  external_product_id VARCHAR(128) NOT NULL,
  analyzer_version VARCHAR(64) NOT NULL,
  request_snapshot_json JSON NOT NULL,
  analysis_snapshot_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user_product (user_id, external_product_id),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fit_feedback (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  analysis_id CHAR(36) NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  external_product_id VARCHAR(128) NOT NULL,
  external_sku_id VARCHAR(128) NOT NULL,
  size_label VARCHAR(32) NOT NULL,
  outcome VARCHAR(16) NOT NULL,
  overall_fit VARCHAR(16) NOT NULL,
  area_feedback_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_training (external_product_id, size_label, overall_fit),
  KEY idx_user (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
