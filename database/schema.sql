CREATE DATABASE IF NOT EXISTS mohan_logistics_lr
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mohan_logistics_lr;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(80) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'operator',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS consignors (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  company_name VARCHAR(160),
  address TEXT,
  city VARCHAR(100),
  state VARCHAR(100),
  pin_code VARCHAR(6),
  gstin VARCHAR(15),
  mobile VARCHAR(15),
  contact_person VARCHAR(120),
  created_at DATETIME NOT NULL,
  INDEX ix_consignors_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS consignees (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  company_name VARCHAR(160),
  address TEXT,
  city VARCHAR(100),
  state VARCHAR(100),
  pin_code VARCHAR(6),
  gstin VARCHAR(15),
  mobile VARCHAR(15),
  contact_person VARCHAR(120),
  created_at DATETIME NOT NULL,
  INDEX ix_consignees_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS lr_sequences (
  sequence_number BIGINT AUTO_INCREMENT PRIMARY KEY,
  allocated_at DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS receipts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  lr_number VARCHAR(32) UNIQUE,
  sequence_number BIGINT UNIQUE,
  cns_serial_number VARCHAR(40),
  receipt_date DATE NOT NULL,
  consignor_id INT NOT NULL,
  consignee_id INT NOT NULL,
  from_station VARCHAR(120),
  to_station VARCHAR(120),
  transit_route VARCHAR(255),
  risk_type VARCHAR(30) NOT NULL,
  trailer_number VARCHAR(40),
  truck_number VARCHAR(40),
  driver_name VARCHAR(120),
  driver_mobile VARCHAR(15),
  load_number VARCHAR(40),
  packing VARCHAR(120),
  package_count INT,
  actual_weight DECIMAL(12,3),
  charged_weight DECIMAL(12,3),
  goods_class VARCHAR(120),
  goods_description TEXT,
  declared_value DECIMAL(14,2) NOT NULL,
  subtotal DECIMAL(14,2) NOT NULL,
  tax_rate DECIMAL(7,4) NOT NULL,
  tax_amount DECIMAL(14,2) NOT NULL,
  grand_total DECIMAL(14,2) NOT NULL,
  payment_type VARCHAR(30) NOT NULL,
  payment_status VARCHAR(20) NOT NULL,
  amount_paid DECIMAL(14,2) NOT NULL,
  balance_due DECIMAL(14,2) NOT NULL,
  payment_remarks TEXT,
  status VARCHAR(20) NOT NULL,
  created_by INT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT fk_receipt_consignor FOREIGN KEY (consignor_id) REFERENCES consignors(id),
  CONSTRAINT fk_receipt_consignee FOREIGN KEY (consignee_id) REFERENCES consignees(id),
  CONSTRAINT fk_receipt_sequence FOREIGN KEY (sequence_number) REFERENCES lr_sequences(sequence_number),
  CONSTRAINT fk_receipt_user FOREIGN KEY (created_by) REFERENCES users(id),
  CONSTRAINT ck_receipts_packages_nonnegative CHECK (package_count IS NULL OR package_count >= 0),
  CONSTRAINT ck_receipts_amounts_nonnegative CHECK (declared_value >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND grand_total >= 0),
  INDEX ix_receipts_receipt_date (receipt_date),
  INDEX ix_receipts_truck_number (truck_number),
  INDEX ix_receipts_status (status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS receipt_particulars (
  id INT AUTO_INCREMENT PRIMARY KEY,
  receipt_id INT NOT NULL,
  serial_no INT NOT NULL,
  chassis_number VARCHAR(80),
  model VARCHAR(100),
  invoice_date DATE,
  shipment_number VARCHAR(80),
  invoice_number VARCHAR(80),
  CONSTRAINT fk_particular_receipt FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE,
  INDEX ix_receipt_particulars_receipt_id (receipt_id),
  INDEX ix_particular_invoice_number (invoice_number),
  INDEX ix_particular_chassis_number (chassis_number)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS receipt_charges (
  id INT AUTO_INCREMENT PRIMARY KEY,
  receipt_id INT NOT NULL,
  charge_name VARCHAR(80) NOT NULL,
  amount DECIMAL(14,2) NOT NULL,
  CONSTRAINT fk_charge_receipt FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE,
  INDEX ix_receipt_charges_receipt_id (receipt_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS receipt_payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  receipt_id INT NOT NULL,
  payment_type VARCHAR(30) NOT NULL,
  amount DECIMAL(14,2) NOT NULL,
  payment_date DATE NOT NULL,
  remarks TEXT,
  CONSTRAINT fk_payment_receipt FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE,
  INDEX ix_receipt_payments_receipt_id (receipt_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS company_settings (
  `key` VARCHAR(80) PRIMARY KEY,
  `value` TEXT NOT NULL,
  updated_at DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  receipt_id INT,
  action VARCHAR(40) NOT NULL,
  details TEXT,
  created_at DATETIME NOT NULL,
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_audit_receipt FOREIGN KEY (receipt_id) REFERENCES receipts(id),
  INDEX ix_audit_logs_created_at (created_at)
) ENGINE=InnoDB;
