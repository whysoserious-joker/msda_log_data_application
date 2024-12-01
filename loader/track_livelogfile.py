import os
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib
import time
import pandas as pd
from queue import Queue
import pymysql
from sqlalchemy import create_engine,event,text
from sqlalchemy import event
import logging
from logging.handlers import RotatingFileHandler
import yaml
import urllib.parse
import warnings
warnings.filterwarnings("ignore")
pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)


logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
# Create a file handler which rotates after every 5 MB
handler = RotatingFileHandler('live_file_log.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class LiveLog:
    def __init__(self, path):
        self.file_path = path

        self.data=[]
        self.last_position = self.load_last_position()
        self.last_hash = None

        with open('config.yml','r') as stream:
            self.config=yaml.safe_load(stream)
    
    def load_last_position(self):
        try:
            with open('statefile.txt', 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0  # Default to the start of the file if no state exists
    
    def save_last_position(self):
        with open('statefile.txt', 'w') as f:
            f.write(str(self.last_position))
        
    def calculate_file_hash(self):
        with open(self.file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() 

    def detect_file_changes(self):
        with open(self.file_path, 'r') as f:
            f.seek(self.last_position)  # Start from the last processed position

            while True:
                current_size = os.path.getsize(self.file_path)
                if current_size < self.last_position:
                    # File was rotated or truncated
                    print("File was rotated or truncated")
                    f.seek(0, os.SEEK_END) 
                    self.last_position = f.tell()
                print(current_size,self.last_position)
                new_lines = f.readlines()
                if new_lines:
                    print("New lines detected:")
                    for line in new_lines:
                        print(line.strip())
                        try:
                            row = json.loads(line)
                            hash_value = self.create_hash(line)
                            d = [
                                row.get("level"),
                                row.get("time"),
                                row.get("sender"),
                                row.get("remote_address"),
                                row.get("username"),
                                row.get("size_bytes"),
                                hash_value,
                            ]
                            self.data.append(d)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON: {e}")
                    print("loading Data .....")
                    # self.load_data()
                self.last_position = f.tell()  # Update the last position
                self.save_last_position()  # Persist the position

                time.sleep(1)


    def mysql_connect(self):
            logger.info("Connecting to mysql...")
            username = self.config['db']['username']
            password = self.config['db']['password']
            hostname = self.config['db']['hostname']
            port = self.config['db']['port']
            database_name = self.config['db']['database_name']
            encoded_password = urllib.parse.quote_plus(password)

            try:
                self.conn = pymysql.connect(host=hostname, port=port, user=username,
                       passwd=encoded_password, db=database_name, autocommit=True)
                
                if self.conn:
                    logger.info("Connected to mysql")
                    print("Connected to mysql")
                    self.cur = self.conn.cursor(pymysql.cursors.DictCursor)
            except Exception as e:
                logger.debug(f"Connection to myqsl Unsuccessful {e}")
                print("Connection to myqsl Unsuccessful", e)


    def load_data(self):
        logger.info("Starting : Load station details")
        self.mysql_connect()
        logger.debug(f"logs data  loading")
        
        insert_sql = """
                        INSERT IGNORE INTO msda_log.logdata
                        VALUES (%s,%s,%s,%s,%s,%s,%s);
                    """
        start_time=time.time()
        dl=len(self.data)
        for i in range(0, dl):
            batch = self.data[i:i + dl]  
            print(len(batch))
            self.cur.executemany(insert_sql, batch)  
        print(f"{len(self.data)} rows processed successfully in {time.time()-start_time}")


    def create_hash(self,log):
        hash_value = hashlib.sha256(log.encode()).hexdigest()
        return hash_value

if __name__ == "__main__":
    folder = 'logs'
    live_log_file = os.path.join(folder, 'sftpgo.log')
    live_log = LiveLog(live_log_file)
    live_log.detect_file_changes()












        # self.last_position = 0
        # self.last_hash = self.calculate_file_hash()

        # while True:
        #     current_hash = self.calculate_file_hash()
        #     current_size = os.path.getsize(self.file_path)

        #     print(self.last_hash,current_hash)
        #     print(self.last_position,current_size)
        #     # Handle file rotation
        #     if current_size < self.last_position:
        #         print("File rotated!")
        #         self.last_position = 0
        #         self.last_hash = current_hash

        #     # Check if file content has changed
        #     if current_hash != self.last_hash:
        #         with open(self.file_path, 'r') as f:
        #             f.seek(self.last_position)  # Move to the last read position
        #             new_lines = f.readlines()  # Read new lines

        #             if new_lines:
        #                 print("New lines detected:")
        #                 for line in new_lines:
        #                     print(line.strip())
        #                     # Process the line as JSON
        #                     try:
        #                         row = json.loads(line)
        #                         hash_value = self.create_hash(line)
        #                         d = [
        #                             row.get("level"),
        #                             row.get("time"),
        #                             row.get("sender"),
        #                             row.get("remote_address"),
        #                             row.get("username"),
        #                             row.get("size_bytes"),
        #                             hash_value,
        #                         ]
        #                         self.data.append(d)
        #                     except json.JSONDecodeError as e:
        #                         print(f"Error decoding JSON: {e}")

        #             self.last_position = f.tell()  # Update position
        #             print("loading data")
        #             self.last_hash = current_hash

        #     time.sleep(1)
    # def detect_file_changes(self):
    #     self.last_position = 0
    #     self.last_hash = self.calculate_file_hash()



    #     while True:
    #         current_hash = self.calculate_file_hash()
    #         current_size = os.path.getsize(self.file_path)

    #         if current_size < self.last_position:
    #             print("File rotated!")
    #             self.last_position = 0
    #             self.last_hash = current_hash

    #         # Check if the file content has changed
    #         if current_hash != self.last_hash:
    #             with open(self.file_path, 'r') as f:
    #                 f.seek(0, os.SEEK_END) 
    #                 self.last_position = f.tell()
    #                 print(self.last_position)
    #             print("File has changed!")
    #             f.seek(self.last_position)  
    #             new_lines = f.readlines()  
    #             if new_lines:
    #                 print("New lines detected:")
    #                 for line in new_lines:
    #                     print(line)
    #                     if line.strip():
    #                         if len(line)>0:
    #                             d=[]
    #                             hash_value=self.create_hash(line)
    #                             row=json.loads(line)
    #                             d.append(row['level'] if 'level' in row else None)
    #                             d.append(row['time'] if 'time' in row else None)
    #                             d.append(row['sender'] if 'sender' in row else None)
    #                             d.append(row['remote_address'] if 'remote_address' in row else None)
    #                             d.append(row['username'] if 'username' in row else None)
    #                             d.append(row['size_bytes'] if 'size_bytes' in row else None)
    #                             d.append(hash_value)
    #                             self.data.append(d)
    #                 print(self.data)
    #                 # self.load_data()
    #                 self.last_position = f.tell()  
    #             self.last_hash = current_hash  
                
    #             time.sleep(1)