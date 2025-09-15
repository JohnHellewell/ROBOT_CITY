# db_handler.py
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
TARGET_DB = os.getenv("TARGET_DB")


def get_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=TARGET_DB
    )


def get_robot_info(robot_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT local_ip, network_port, robot_type, color, CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE, " \
            "steering_limit, forward_limit, weapon_limit, bidirectional_weapon FROM robot " \
            "JOIN robot_type ON robot.robot_type = robot_type.bot_type WHERE robot_id = %s",
            (robot_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return (
                result['local_ip'],
                int(result['network_port']),
                [bool(result['CH1_INVERT']), bool(result['CH2_INVERT']), bool(result['CH3_INVERT']), bool(result['INVERT_DRIVE'])],
                [float(result['steering_limit']), float(result['forward_limit']), float(result['weapon_limit']), bool(result['bidirectional_weapon'])]
            )
        else:
            return None
    except mysql.connector.Error as err:
        print("Database error:", err)
        return None


def add_robot():
    try:
        robot_id = input("Enter robot ID: ").strip()
        local_ip = input("Enter local IP address: ").strip()
        port = int(input("Enter network port: ").strip())
        ch1_inv = input("Invert CH1? (y/n): ").strip().lower() == 'y'
        ch2_inv = input("Invert CH2? (y/n): ").strip().lower() == 'y'
        ch3_inv = input("Invert CH3? (y/n): ").strip().lower() == 'y'
        invert_drive = input("Invert drive? (y/n): ").strip().lower() == 'y'
        robot_type = input("Enter robot type: ").strip()
        color = input("Enter color: ").strip()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO robot (robot_id, local_ip, network_port, CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE, robot_type, color)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (robot_id, local_ip, port, ch1_inv, ch2_inv, ch3_inv, invert_drive, robot_type, color))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Robot '{robot_id}' added successfully.")

    except mysql.connector.IntegrityError:
        print("Error: Robot ID already exists.")
    except ValueError:
        print("Invalid number input.")
    except Exception as e:
        print("Error adding robot:", e)


def remove_robot():
    robot_id = input("Enter robot ID to remove: ").strip()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM robot WHERE robot_id = %s", (robot_id,))
        if cursor.rowcount == 0:
            print(f"No robot found with ID '{robot_id}'.")
        else:
            conn.commit()
            print(f"Robot '{robot_id}' removed successfully.")
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error removing robot:", e)


def edit_robot():
    robot_id = input("Enter robot ID to edit: ").strip()
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM robot WHERE robot_id = %s", (robot_id,))
        robot = cursor.fetchone()
        if not robot:
            print(f"No robot found with ID '{robot_id}'.")
            cursor.close()
            conn.close()
            return

        print("Leave blank to keep current value.")
        new_ip = input(f"Current IP is {robot['local_ip']}. New IP: ").strip()
        new_port_input = input(f"Current port is {robot['network_port']}. New port: ").strip()
        new_robot_type = input(f"Current bot type is {robot['robot_type']}. New bot type: ").strip()
        new_color = input(f"Current color is {robot['color']}. New color: ").strip()
        new_invert_drive = input(f"Current invert_drive is {bool(robot['INVERT_DRIVE'])}. Only change this if robot turns when supposed to go forward. (y/n): ").strip().lower()
        new_ch1_inv = input(f"Current CH1 invert is {bool(robot['CH1_INVERT'])} (y/n): ").strip().lower()
        new_ch2_inv = input(f"Current CH2 invert is {bool(robot['CH2_INVERT'])} (y/n): ").strip().lower()
        new_ch3_inv = input(f"Current CH3 invert is {bool(robot['CH3_INVERT'])} (y/n): ").strip().lower()

        # If user left blank, keep old values
        ip = new_ip if new_ip else robot['local_ip']
        port = int(new_port_input) if new_port_input else robot['network_port']
        robot_type = new_robot_type if new_robot_type else robot['robot_type']
        color = new_color if new_color else robot['color']
        invert_drive = robot['INVERT_DRIVE'] if new_invert_drive == '' else (new_invert_drive == 'y')
        ch1_inv = robot['CH1_INVERT'] if new_ch1_inv == '' else (new_ch1_inv == 'y')
        ch2_inv = robot['CH2_INVERT'] if new_ch2_inv == '' else (new_ch2_inv == 'y')
        ch3_inv = robot['CH3_INVERT'] if new_ch3_inv == '' else (new_ch3_inv == 'y')

        cursor.execute("""
            UPDATE robot
            SET local_ip = %s,
                network_port = %s,
                robot_type = %s,
                color = %s,
                INVERT_DRIVE = %s,
                CH1_INVERT = %s,
                CH2_INVERT = %s,
                CH3_INVERT = %s
            WHERE robot_id = %s
        """, (ip, port, robot_type, color, invert_drive, ch1_inv, ch2_inv, ch3_inv, robot_id))

        conn.commit()
        print(f"Robot '{robot_id}' updated successfully.")
        cursor.close()
        conn.close()

    except Exception as e:
        print("Error editing robot:", e)


def show_robots():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                robot_id, local_ip, network_port, robot_type, color,
                CH1_INVERT, CH2_INVERT, CH3_INVERT, INVERT_DRIVE,
                steering_limit, forward_limit, weapon_limit, bidirectional_weapon
            FROM robot
            JOIN robot_type ON robot.robot_type = robot_type.bot_type
        """)

        robots = cursor.fetchall()
        cursor.close()
        conn.close()

        if not robots:
            print("No robots found in database.")
            return

        # Map database columns to shorter display names
        display_map = {
            'robot_id': 'ID',
            'local_ip': 'IP',
            'network_port': 'Port',
            'robot_type': 'Type',
            'color': 'Color',
            'CH1_INVERT': 'ch1_inv',
            'CH2_INVERT': 'ch2_inv',
            'CH3_INVERT': 'ch3_inv',
            'INVERT_DRIVE': 'inv_drv',
            'steering_limit': 'steer_lim',
            'forward_limit': 'for_lim',
            'weapon_limit': 'wpn_lim',
            'bidirectional_weapon': 'bi_dir_wpn'
        }

        # Set maximum column widths
        max_widths = {
            'robot_id': 6,
            'local_ip': 15,
            'network_port': 5,
            'robot_type': 12,
            'color': 8,
            'CH1_INVERT': 5,
            'CH2_INVERT': 5,
            'CH3_INVERT': 5,
            'INVERT_DRIVE': 5,
            'steering_limit': 6,
            'forward_limit': 6,
            'weapon_limit': 6,
            'bidirectional_weapon': 5
        }

        # Print header
        header = ""
        for col in display_map:
            header += display_map[col].ljust(max_widths[col]+2)
        print(header)
        print("-" * len(header))

        # Print rows
        for r in robots:
            row_str = ""
            for col, width in max_widths.items():
                val = r[col]
                # convert booleans to True/False
                if isinstance(val, bool) or col in ['CH1_INVERT','CH2_INVERT','CH3_INVERT','INVERT_DRIVE','bidirectional_weapon']:
                    val = str(bool(val))
                val = str(val)
                # truncate if too long
                if len(val) > width:
                    val = val[:width-3] + "..."
                row_str += val.ljust(width+2)
            print(row_str)

    except Exception as e:
        print("Error showing robots:", e)
