-- creates tables for the Combat Robot Arcade DB

USE ROBOT_CITY;

DROP DATABASE IF EXISTS ROBOT_CITY;

CREATE DATABASE ROBOT_CITY;

USE ROBOT_CITY;

CREATE TABLE robot_type (
    bot_type VARCHAR(20) PRIMARY KEY,
    steering_limit FLOAT DEFAULT 1.0,
    forward_limit FLOAT DEFAULT 1.0,
    weapon_limit FLOAT DEFAULT 0.4,
    bidirectional_weapon BOOLEAN DEFAULT 0,
    CHECK (steering_limit >= 0.0 AND steering_limit <= 1.0),
    CHECK (forward_limit >= 0.0 AND forward_limit <= 1.0),
    CHECK (weapon_limit >= 0.0 AND weapon_limit <= 1.0)
);

CREATE TABLE robot (
    robot_id int PRIMARY KEY,
    local_ip VARCHAR(13) NOT NULL,
    network_port SMALLINT NOT NULL,
    robot_type VARCHAR(20) NOT NULL,
    color ENUM('YELLOW', 'BLUE', 'GREEN', 'ORANGE', 'PINK') NOT NULL,
    CH1_INVERT BOOLEAN DEFAULT 0,
    CH2_INVERT BOOLEAN DEFAULT 0,
    CH3_INVERT BOOLEAN DEFAULT 0,
    INVERT_DRIVE BOOLEAN DEFAULT 0,
    FOREIGN KEY (robot_type) REFERENCES robot_type(bot_type)
);


