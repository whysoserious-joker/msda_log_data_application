import os
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib
import time
import pandas as pd
from queue import Queue
from datetime import datetime
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
handler = RotatingFileHandler('track_log.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class load_to_db:
    def __init__(self,configfile='../config.yml'):
        with open(configfile,'r') as stream:
            self.config=yaml.safe_load(stream)
        self.conn=None
        self.cur=None
        self.database_name = self.config['db']['database_name']
        self.table_name= self.config['db']['table_name']

        self.check_table_exists(self.database_name,self.table_name)

    def mysql_connect(self):
            # connect to database
            logger.info("Connecting to mysql...")
            username = self.config['db']['username']
            password = self.config['db']['password']
            hostname = self.config['db']['hostname']
            port = self.config['db']['port']
            encoded_password = urllib.parse.quote_plus(password)

            try:
                self.conn = pymysql.connect(host=hostname, port=port, user=username,
                       passwd=encoded_password, db=self.database_name, autocommit=True)
                
                if self.conn:
                    logger.info("Connected to mysql")
                    print("Connected to mysql")
                    self.cur = self.conn.cursor(pymysql.cursors.DictCursor)
            except Exception as e:
                logger.debug(f"Connection to myqsl Unsuccessful {e}")
                print("Connection to myqsl Unsuccessful", e)

    def check_table_exists(self,dbname,tablename):
        if not self.conn or not self.cur:
            self.mysql_connect()

        try:
            table_exists_sql=f'''
                        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_SCHEMA = '{dbname}' AND TABLE_NAME = '{tablename}';
                        '''
            self.cur.execute(table_exists_sql)
            result = self.cur.fetchone()  # Fetch one row, if it exists
            
            if result:
                print("Table already exists")
                logger.info(f"Table '{tablename}' exists in database '{dbname}'.")
                return True
            else:
                print(f"Table {tablename} does not exist in database {dbname}")
                logger.warning(f"Table '{tablename}' does not exist in database '{dbname}'.")
                return self.create_table(tablename)
                
        except Exception as e:
            logger.error(f"Error checking if table exists: {e}")
            return False
    
    def create_table(self, tablename):
        try:
            print(f"Creating Table '{tablename}'.")
            logger.info(f"Creating Table '{tablename}'.")
            
            create_sql = f'''
                CREATE TABLE `{tablename}` (
                    `level` varchar(100) NOT NULL,
                    `time` timestamp NOT NULL,
                    `sender` varchar(100) NOT NULL,
                    `remote_address` varchar(200) NOT NULL,
                    `username` varchar(200) NOT NULL,
                    `size_bytes` int NOT NULL,
                    `hash_value` varchar(256) NOT NULL,
                    `batch_load_timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`hash_value`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            '''
            
            logger.debug(f"Executing table creation SQL: {create_sql}")
            self.cur.execute(create_sql)
            logger.info(f"Table '{tablename}' created successfully.")
            return True

        except pymysql.Error as e:
            logger.error(f"Error creating table '{tablename}': {e}")
            print(f"Failed to create table '{tablename}': {e}")
            return False

    def load_data_to_db(self,data,batch_size=500):

        if not self.conn or not self.cur:
            self.mysql_connect()
        
        insert_sql = f"""
            INSERT IGNORE INTO {self.database_name+"."+self.table_name}
            VALUES (%s, %s, %s, %s, %s, %s, %s,%s);
        """
        logger.info(f"Starting :{len(data)} rows to database")
        start_time=time.time()

        dl=len(data)
        for i in range(0, dl,batch_size):
            batch = data[i:i + batch_size]  
            self.cur.executemany(insert_sql, batch)  
        logger.info(f"{len(data)} rows inserted in {time.time() - start_time:.2f} seconds.")
    

    def create_file_if_not_exists(self,file_path,content):
        """
        Creates a file if it doesn't exist.
        :param file_path: Path to the file
        """
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                # Optionally write initial content to the file
                file.write(content)
            print(f"File '{file_path}' created.")
        else:
            print(f"File '{file_path}' already exists.")

class TrackLiveLog(load_to_db):
    def __init__(self, filepath,statefile):
        super().__init__()
        self.filepath=filepath
        self.data=[]
        self.statefile=statefile
        self.last_position=self.load_last_position()
        self.last_hash = None
        
    
    def load_last_position(self):

        self.create_file_if_not_exists(self.statefile,'0')
        try:
            with open(self.statefile, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0  # Default to the start of the file if no state exists

    def save_last_position(self):
        with open(self.statefile, 'w') as f:
            f.write(str(self.last_position))
        
    def detect_file_changes(self):
        with open(self.filepath, 'r') as f:
            f.seek(self.last_position)  # Start from the last processed position
        
            current_size = os.path.getsize(self.filepath)
            # print(current_size,self.last_position)

            if current_size < self.last_position:
                # File was rotated or truncated
                print("File was rotated or truncated")
                f.seek(0, os.SEEK_END) 
                self.last_position = f.tell()
            
            new_lines = f.readlines()
            if new_lines:
                script_start_time = datetime.now()
                print("New lines detected:")
                for line in new_lines:
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
                            script_start_time.strftime('%Y-%m-%d %H:%M:%S')

                        ]
                        self.data.append(d)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")
                print("loading live file Data .....",len(self.data))
                self.load_data()
                self.data=[]
               
            self.last_position = f.tell()  # Update the last position
            self.save_last_position()  # Persist the position

            time.sleep(1)

    def create_hash(self,log):
        hash_value = hashlib.sha256(log.encode()).hexdigest()
        return hash_value
    
    def load_data(self):
        self.load_data_to_db(self.data)

class TrackFolder(load_to_db):
    def __init__(self,folderpath,logfile,processed_statefile):
        super().__init__()
        self.folderpath=folderpath
        self.logfile=logfile
        self.processed_statefile=processed_statefile
        self.processed_files=[]
        self.data=[]

        self.previous_loaded_files()
        self.process_files()

    def previous_loaded_files(self):
        self.create_file_if_not_exists(self.processed_statefile,'')
        p=open(self.processed_statefile,'r')
        for line in p:
            entry=json.loads(line.strip())
            self.processed_files.append(entry['file'])

    def process_files(self):
        self.previous_loaded_files()
        
        p=open(self.processed_statefile,'a')

        # print(self.processed_files)
        for file in os.listdir(self.folderpath):
            if (file != self.logfile) and (file not in self.processed_files):
                logger.debug(f"processing file {file}")
                print("processing",file)
                self.read_file(file)
                json.dump({'file':file,'timestamp':time.time()},p)
                p.write('\n')
        
        if len(self.data)>0:
            self.load_data()
            self.data=[]    

    def read_file(self,file):
        file_path=os.path.join(self.folderpath,file)
        if '.log' in file_path:
            f=open(file_path,'r')
            s=f.read()
            lines=s.split("\n")

            script_start_time = datetime.now()
            for line in lines:
                if len(line)>0:
                    d=[]
                    hash_value=self.create_hash(line)
                    row=json.loads(line)
                    d.append(row['level'] if 'level' in row else None)
                    d.append(row['time'] if 'time' in row else None)
                    d.append(row['sender'] if 'sender' in row else None)
                    d.append(row['remote_address'] if 'remote_address' in row else None)
                    d.append(row['username'] if 'username' in row else None)
                    d.append(row['size_bytes'] if 'size_bytes' in row else None)
                    d.append(hash_value)
                    d.append(script_start_time.strftime('%Y-%m-%d %H:%M:%S'))
                    self.data.append(d)

    def create_hash(self,log):
        hash_value = hashlib.sha256(log.encode()).hexdigest()
        return hash_value

    def load_data(self):
        self.load_data_to_db(self.data)


class LogFileHandler(FileSystemEventHandler):
    def __init__(self, processed_files,queue):
        self.processed_files = processed_files
        self.queue=queue

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path in self.processed_files:
            return
        else:
            self.queue.put(event.src_path)

if __name__ == "__main__":

    configfile='../config.yml'
    with open(configfile,'r') as stream:
            config=yaml.safe_load(stream)

    logdir = config['folder']['path']
    processed_state_files = config['folder']['processed_files']

    livelogfile = config['livefile']['filename']
    statefile=config['livefile']['statefile']
    livelogfile_path = os.path.join(logdir,livelogfile)

    livelog = TrackLiveLog(livelogfile_path,statefile)
    trackfolder=TrackFolder(logdir,livelogfile,processed_state_files)
    processed_files=trackfolder.processed_files


    file_queue = Queue()
    event_handler = LogFileHandler(processed_files,file_queue)
    observer = Observer()
    observer.schedule(event_handler, logdir, recursive=False)
    observer.start()

    try:
        while True:
            
            livelog.detect_file_changes()

            if not file_queue.empty():
                new_file_path = file_queue.get()
                print(f"New log file detected: {new_file_path}")
                trackfolder.process_files()

            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()