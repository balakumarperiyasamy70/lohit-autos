-- Lohit Enterprises LLC — Used Car Dealer Database Schema
-- Run: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS lohit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lohit;

CREATE TABLE admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_number VARCHAR(30) NOT NULL UNIQUE,
    vin VARCHAR(20),
    year INT NOT NULL,
    make VARCHAR(60) NOT NULL,
    model VARCHAR(80) NOT NULL,
    trim VARCHAR(80),
    body_type VARCHAR(40),               -- Sedan, SUV, Truck, Coupe, Van, etc.
    mileage INT DEFAULT 0,
    price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    exterior_color VARCHAR(40),
    interior_color VARCHAR(40),
    transmission VARCHAR(30),            -- Automatic, Manual
    drivetrain VARCHAR(20),              -- FWD, RWD, AWD, 4WD
    fuel_type VARCHAR(20),               -- Gasoline, Diesel, Hybrid, Electric
    engine VARCHAR(60),
    doors INT,
    cylinders VARCHAR(10),
    mpg_city INT,
    mpg_highway INT,
    description TEXT,
    featured TINYINT(1) DEFAULT 0,
    status ENUM('available','pending','sold') DEFAULT 'available',
    main_image VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_make (make),
    INDEX idx_featured (featured)
);

CREATE TABLE vehicle_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sort_order INT DEFAULT 0,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
);

CREATE TABLE leads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lead_type ENUM('inquiry','financing','tradein','contact') NOT NULL DEFAULT 'inquiry',
    vehicle_id INT,                      -- nullable: inquiry about a specific vehicle
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(30),
    message TEXT,
    -- financing pre-qualify fields
    employment_status VARCHAR(60),
    monthly_income DECIMAL(10,2),
    credit_estimate VARCHAR(40),         -- Excellent, Good, Fair, Poor, Not Sure
    down_payment DECIMAL(10,2),
    -- trade-in / sell-your-car fields
    trade_year INT,
    trade_make VARCHAR(60),
    trade_model VARCHAR(80),
    trade_mileage INT,
    trade_condition VARCHAR(40),         -- Excellent, Good, Fair, Poor
    status ENUM('new','contacted','closed') DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
    INDEX idx_lead_status (status),
    INDEX idx_lead_type (lead_type)
);

-- Default admin (password set during deployment — see deploy/setup.md step 5)
INSERT INTO admin_users (username, password_hash) VALUES
('admin', 'pbkdf2:sha256:600000$placeholder$placeholder');

-- Sample inventory (edit or delete from the admin panel once live)
INSERT INTO vehicles
(stock_number, vin, year, make, model, trim, body_type, mileage, price,
 exterior_color, interior_color, transmission, drivetrain, fuel_type, engine,
 doors, cylinders, mpg_city, mpg_highway, description, featured, status) VALUES
('LE1001', '1HGCM82633A004352', 2018, 'Honda', 'Accord', 'EX-L', 'Sedan', 62450, 18995.00,
 'Modern Steel', 'Black', 'Automatic', 'FWD', 'Gasoline', '1.5L Turbo I4',
 4, '4', 30, 38, 'Well-maintained one-owner Accord EX-L with leather seats, sunroof, and Honda Sensing safety suite. Clean CARFAX. Fresh oil change and new tires.', 1, 'available'),
('LE1002', '3GNAXUEV5LS606721', 2020, 'Chevrolet', 'Equinox', 'LT', 'SUV', 41200, 21495.00,
 'Summit White', 'Jet Black', 'Automatic', 'AWD', 'Gasoline', '1.5L Turbo I4',
 4, '4', 26, 31, 'Roomy AWD Equinox LT, perfect for Arkansas winters. Apple CarPlay, backup camera, remote start. Excellent condition inside and out.', 1, 'available'),
('LE1003', '1FTEW1EP5JFA12345', 2019, 'Ford', 'F-150', 'XLT', 'Truck', 78900, 28995.00,
 'Oxford White', 'Medium Earth Gray', 'Automatic', '4WD', 'Gasoline', '3.5L EcoBoost V6',
 4, '6', 18, 24, 'Capable F-150 XLT SuperCrew 4x4 with tow package and bed liner. Strong service history, ready to work or haul the family.', 1, 'available'),
('LE1004', '5NPD84LF2KH123456', 2019, 'Hyundai', 'Elantra', 'SEL', 'Sedan', 55300, 14495.00,
 'Galactic Gray', 'Gray', 'Automatic', 'FWD', 'Gasoline', '2.0L I4',
 4, '4', 31, 41, 'Fuel-efficient and dependable Elantra SEL. Great first car or commuter with low miles for the year. Bluetooth, lane-keep assist.', 0, 'available'),
('LE1005', '1C4RJFBG6KC712345', 2019, 'Jeep', 'Grand Cherokee', 'Limited', 'SUV', 68100, 25995.00,
 'Diamond Black', 'Black', 'Automatic', '4WD', 'Gasoline', '3.6L V6',
 4, '6', 19, 26, 'Luxurious Grand Cherokee Limited with heated leather, panoramic roof, and premium audio. Rugged 4WD capability meets comfort.', 0, 'available'),
('LE1006', '2T1BURHE0JC123789', 2018, 'Toyota', 'Corolla', 'LE', 'Sedan', 71500, 13995.00,
 'Classic Silver', 'Ash', 'Automatic', 'FWD', 'Gasoline', '1.8L I4',
 4, '4', 30, 40, 'Legendary Toyota reliability. This Corolla LE is a proven commuter with Toyota Safety Sense, backup camera, and great fuel economy.', 0, 'available');
