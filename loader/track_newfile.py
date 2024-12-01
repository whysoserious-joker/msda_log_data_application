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
handler = RotatingFileHandler('new_file_log.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class process_existing_files:
    def __init__(self,path,log_file,statefile):
        self.path=path
        self.log_file=log_file
        self.processed_files=[]
        self.data=[]
        self.df=None
        self.statefile=statefile

        with open('config.yml','r') as stream:
            self.config=yaml.safe_load(stream)

            
        self.previous_loaded_files()
        self.process_files()

    def previous_loaded_files(self):
        p=open(self.statefile,'r')
        for line in p:
            entry=json.loads(line.strip())
            self.processed_files.append(entry['file'])
        
        print(self.processed_files)



    def process_files(self):
        self.previous_loaded_files()
        p=open(self.statefile,'a')

        for file in os.listdir(self.path):
            if (file != self.log_file) and (file not in self.processed_files):
                logger.debug(f"processing file {file}")
                print("processing",file)
                self.read_file(file)
                json.dump({'file':file,'timestamp':time.time()},p)
                p.write('\n')
        
        print(self.data[0:10])
        self.load_data()

    def read_file(self,file):
        file_path=os.path.join(self.path,file)
        if '.log' in file_path:
            f=open(file_path,'r')
            s=f.read()
            lines=s.split("\n")

            
            
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
                    self.data.append(d)




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
        batch_size = 500
        start_time=time.time()
        for i in range(0, len(self.data), batch_size):
            batch = self.data[i:i + batch_size]  
            self.cur.executemany(insert_sql, batch)  
        print(f"{len(self.data)} rows inserted successfully in {time.time()-start_time}")
    
    def create_hash(self,log):
        hash_value = hashlib.sha256(log.encode()).hexdigest()
        return hash_value
        

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
    state_file = 'processed_logs.json'
    log_dir = "logs"
    log_file = "sftpgo.log"

    f=process_existing_files(log_dir,log_file,state_file)
    processed_files=f.processed_files

    file_queue = Queue()
    event_handler = LogFileHandler(processed_files,file_queue)
    observer = Observer()
    observer.schedule(event_handler, log_dir, recursive=False)
    observer.start()

    try:
        while True:
            if not file_queue.empty():
                new_file_path = file_queue.get()
                print(f"New log file detected: {new_file_path}")
                f.process_files()

            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()



















            # connection_string = f'mysql+pymysql://{username}:{encoded_password}@{hostname}:{port}/{database_name}'
            # print(connection_string)
            # try:
            #     self.engine = create_engine(connection_string)
            #     self.engine.connect()
            #     logger.info("Connected to mysql")
            #     print("Connected to mysql")
            # except Exception as e:
            #     logger.debug(f"Connection to myqsl Unsuccessful {e}")
            #     print("Connection to myqsl Unsuccessful", e)

            # @event.listens_for(self.engine, "before_cursor_execute")
            # def receive_before_cursor_execute(
            #     conn, cursor, statement, params, context, executemany
            #         ):
            #             if executemany:
            #                 cursor.fast_executemany = True