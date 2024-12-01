# msda_log_data_application

This application tracks MSDA Clarkson server live. It also stores historical activities , how many users accessed this server,how many bytes were transfered,  how many transfers, uploads , downloads by each user and also captures activities trend.

This implementation outlines a system for tracking and processing logs in real-time, handling both individual log file updates and the addition of new log folders. Below is a breakdown of the code, challenges, and solutions.

![Alt text](Images/msda_app.png)

## log data description

We have a folder where it a has bunch of log files and also the live log file which captures activites on site live.
Once this live log file reaches the size of 10.5 MB , it renames the file to that date and stores in the same folder. Once again live log file keeps track of activities and this process goes on.

- log folder: loader/logs
- live log file : loader/logs/sftpgo.log

logdata sample:

![Alt text](Images/log.png)


## Objective

- Live Log Tracking: Monitor a live log file (sftpgo.log) for new entries and process them as they are added.
- Folder Monitoring: Detect and process new folders added to a specified directory (logs).d.

**Challenges**

- Duplicate rows shouldnt be processed 
- if the tracker script fails at some point it should pick up from where it left
- we don't have a unique identifier for a log entry , because timestamp has milliseconds and there might be duplicates even at millisecond.

## Live log tracker script

*track_livelogfile.py*

Import necessary packages

```python
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
```

setup the logger file to keep track of our process

```python
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
# Create a file handler which rotates after every 5 MB
handler = RotatingFileHandler('live_file_log.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

There are four functions which handles this live log file

```python
    def load_last_position(self):
        try:
            with open('statefile.txt', 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0  # Default to the start of the file if no state exists
```

I have created a statefile which is used to store the last position of the live log file.The above function retrieves the last position from the statefile.

```python
    def save_last_position(self):
        with open('statefile.txt', 'w') as f:
            f.write(str(self.last_position))
```

The above function is to store or save the new last position of the live log file.

```python
    def calculate_file_hash(self):
        with open(self.file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest() 
```

The above function creates a hash for the whole file , which helps us to know if the file has changed which means new entries or the file has been rotated.

```python
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
```

The above function detects any changes in the file and processes the new entries.
- It starts from last processed position , here position means the byte info of the last position which can also be interpreted as file size. 

- We calculate the current file size and compare to the last processed position , if its lesser that means the file was rotated or truncated. Then we save the last position. 

- If the file has rotated and new lines are added , it captures them from the last poition that we have saved. It reads all the lines and updated the last postion simulatniously.

- As and when new lines are read it is processed using the below function.

```python
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
```



```python
if __name__ == "__main__":
    folder = 'logs'
    live_log_file = os.path.join(folder, 'sftpgo.log')
    live_log = LiveLog(live_log_file)
    live_log.detect_file_changes()
```
