-- creates tables for the Combat Robot Arcade DB

USE ROBOT_CITY;

DROP TABLE IF EXISTS robot;

CREATE TABLE robot (
    robot_id int PRIMARY KEY,
    local_ip VARCHAR(13) NOT NULL,
    network_port SMALLINT NOT NULL,
    robot_type VARCHAR(20),
    color VARCHAR(20),
    CH1_INVERT BOOLEAN DEFAULT 0,
    CH2_INVERT BOOLEAN DEFAULT 0,
    CH3_INVERT BOOLEAN DEFAULT 0
);

DROP TABLE IF EXISTS controller;

CREATE TABLE controller (
    controller_id VARCHAR(40) PRIMARY KEY,
    x_axis float,
    y_axis float
);

CREATE TABLE battle_history (
    battle_id INT PRIMARY KEY AUTO_INCREMENT,
    date_time datetime,
    player1_bot INT,
    player2_bot INT,
    player3_bot INT,
    player4_bot INT,
    winner INT,
    FOREIGN KEY (player1_bot) REFERENCES robot (robot_id),
    FOREIGN KEY (player2_bot) REFERENCES robot (robot_id),
    FOREIGN KEY (player3_bot) REFERENCES robot (robot_id),
    FOREIGN KEY (player4_bot) REFERENCES robot (robot_id)
)
