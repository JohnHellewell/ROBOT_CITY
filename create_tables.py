import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

#load .env values
load_dotenv()
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
TARGET_DB = os.getenv("TARGET_DB")

CREATE_DB_PATH = 'create_tables.sql'
FILL_DATA_PATH = 'fill_tables.sql'

def get_connection(database=None):
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=TARGET_DB
    )

def execute_sql_file(cursor, sql_file_path):
    with open(sql_file_path, 'r') as file:
        sql_commands = file.read()

    for command in sql_commands.split(';'):
        command = command.strip()
        
        try:
            cursor.execute(command)
        except Error as e:
                print(e)

#main
try:
    response = input(f"This will drop and reset all data in the {TARGET_DB} database. " \
    "Are you sure you want to continue? (y/n): ").strip().lower()

    if response != 'y':
        print("Operation cancelled.")
        exit()
        

    #get connection to db
    conn = get_connection()
    cursor = conn.cursor()

    #create tables
    execute_sql_file(cursor, CREATE_DB_PATH)
    conn.commit()
    print("Tables created")

    #Fill tables with data
    execute_sql_file(cursor, FILL_DATA_PATH)
    conn.commit()
    print("Tables filled with data")


except Error as e:
    print(e)

cursor.close()
conn.close()