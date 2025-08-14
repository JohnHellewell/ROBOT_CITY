USE ROBOT_CITY;

INSERT INTO robot_type (bot_type, steering_limit, forward_limit, weapon_limit, bidirectional_weapon)
VALUES  ('DRUM', 0.6, 1.0, 0.4, 1),
        ('HORIZONTAL', 0.6, 1.0, 0.4, 0),
        ('VERTICAL', 0.3, 0.4, 0.4, 1),
        ('LIFTER', 1.0, 1.0, 1.0, 0);

INSERT INTO Robot (robot_id, local_ip, network_port, robot_type, color, CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE)
VALUES  (10, "192.168.8.10", 4210, "DRUM", "YELLOW", 0, 1, 1, 0),
        (11, "192.168.8.11", 4211, "DRUM", "BLUE", 0, 1, 1, 0),
        (12, "192.168.8.12", 4212, "DRUM", "ORANGE", 0, 1, 1, 0),
        (13, "192.168.8.13", 4213, "DRUM", "GREEN", 0, 1, 1, 0),
        (20, "192.168.8.20", 4220, "HORIZONTAL", "YELLOW", 0, 0, 0, 0), 
        (30, "192.168.8.30", 4230, "VERTICAL", "YELLOW", 0, 0, 0, 0);   
