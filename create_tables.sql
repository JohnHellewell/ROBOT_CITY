-- creates tables for the Combat Robot Arcade DB

USE ROBOT_CITY;

DROP TABLE IF EXISTS Robot;

CREATE TABLE Robot (
    robot_id int PRIMARY KEY,
    local_ip_address VARCHAR(13) NOT NULL,
    network_port SMALLINT NOT NULL,
    robot_type VARCHAR(20),
    color VARCHAR(20)
);

DROP TABLE IF EXISTS Controller;

CREATE TABLE Controller (
    controller_id VARCHAR(20) PRIMARY KEY,
    x_axis float,
    y_axis float
);
