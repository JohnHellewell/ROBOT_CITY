USE ROBOT_CITY;

INSERT INTO Robot (robot_id, local_ip, network_port, robot_type, color, CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE)
VALUES  (10, "192.168.8.10", 4210, "DRUM", "YELLOW", 0, 1, 1, 0),
        (11, "192.168.8.11", 4211, "DRUM", "BLUE", 0, 1, 1, 0),
        (12, "192.168.8.12", 4212, "DRUM", "ORANGE", 0, 1, 1, 0),
        (13, "192.168.8.13", 4213, "DRUM", "GREEN", 0, 1, 1, 0),
        (20, "192.168.8.20", 4220, "HORIZONTAL", "YELLOW", 0, 0, 0, 0), --not sure about inverse values
        (30, "192.168.8.30", 4230, "VERTICAL", "YELLOW", 0, 0, 0, 0);   --not sure about inverse values
