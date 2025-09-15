# db_handler.py
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
from tabulate import tabulate

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


from tabulate import tabulate

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

        # Convert rows to list of lists and handle booleans
        table = []
        for r in robots:
            row = []
            for col in display_map.keys():
                val = r[col]
                if isinstance(val, bool) or col in ['CH1_INVERT','CH2_INVERT','CH3_INVERT','INVERT_DRIVE','bidirectional_weapon']:
                    val = "Yes" if val else "No"
                row.append(val)
            table.append(row)

        # Print table with tabulate
        print(tabulate(table, headers=display_map.values(), tablefmt="fancy_grid"))

    except Exception as e:
        print("Error showing robots:", e)


def show_types():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM robot_type")

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            print("No robots found in database.")
            return

        # Shorten column names for display
        headers = {
            "bot_type": "Type",
            "steering_limit": "Steer",
            "forward_limit": "Fwd",
            "weapon_limit": "Weapon",
            "bidirectional_weapon": "Bi-Weap"
        }

        # Convert rows to list of tuples in order of headers
        table = []
        for row in rows:
            table.append([row[k] for k in headers.keys()])

        # Display table
        print(tabulate(table, headers=headers.values(), tablefmt="fancy_grid"))

    except Exception as e:
        print("Error showing robot types:", e)

def edit_type():
    robot_id = input("Enter robot type to edit: (DRUM, HORIZONTAL, VERTICAL, LIFTER) ").strip()
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM robot_type WHERE bot_type = %s", (robot_id,))
        robot_type = cursor.fetchone()
        if not robot_type:
            print(f"No robot type found with ID '{robot_id}'.")
            cursor.close()
            conn.close()
            return

        print("Leave blank to keep current value.")
        new_steer_limit = input(f"Current steering limit is {robot_type['steering_limit']}. New limit: ").strip()
        new_forw_limit = input(f"Current forward limit is {robot_type['forward_limit']}. New limit: ").strip()
        new_weap_limit = input(f"Current weapon limit is {robot_type['weapon_limit']}. New limit: ").strip()
        new_bidir_weap = input(f"Current CH3 invert is {bool(robot_type['bidirectional_weapon'])}. Note: ESC settings must match this value. Set to true? (y/n): ").strip().lower()

        # If user left blank, keep old values
        steer_limit = float(new_steer_limit) if new_steer_limit else robot_type['steering_limit']
        forw_limit = float(new_forw_limit) if new_forw_limit else robot_type['forward_limit']
        weap_limit = float(new_weap_limit) if new_weap_limit else robot_type['weapon_limit']
        bidir_weap = robot_type['bidirectional_weapon'] if new_bidir_weap == '' else (new_bidir_weap == 'y')

        #constrain all floats between 0.0 and 1.0
        steer_limit = max(0.0, min(1.0, steer_limit))
        forw_limit = max(0.0, min(1.0, forw_limit))
        weap_limit = max(0.0, min(1.0, weap_limit))

        cursor.execute("""
            UPDATE robot_type
            SET steering_limit = %s,
                forward_limit = %s,
                weapon_limit = %s,
                bidirectional_weapon = %s
            WHERE bot_type = %s
        """, (steer_limit, forw_limit, weap_limit, bidir_weap, robot_id))

        conn.commit()
        print(f"Robot type'{robot_id}' updated successfully.")
        cursor.close()
        conn.close()
    
    except Exception as e:
        print("Error editing robot type:", e)