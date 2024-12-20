# msda_log_data_application
## Log Tracking System for Live and Folder Updates

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
- Folder Monitoring: Detect and process new folders added to a specified directory (logs).

**Challenges**

- Duplicate rows shouldnt be processed 
- if the tracker script fails at some point it should pick up from where it left
- we don't have a unique identifier for a log entry , because timestamp has milliseconds and there might be duplicates even at millisecond.


## Code Explanation

Import all the libraries

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
```

Set up your logger file which keeps track of the steps this script does.

```python
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
# Create a file handler which rotates after every 5 MB
handler = RotatingFileHandler('track_log.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

**class load_to_db** 

- *mysql_connect()* method connects to the database using the parameters from config file.
```python
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
```

- *check_table_exists* method recieves dbname and table name as arguments and checks if the table exists in the database. If not , it creates a table using the createtable statement.

```python
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
```


- If table already exixts and *load_data_to_db()** is called with passing data as argument it loads the data to the database table using execute many and insert ignore to handle the duplicates.

```python
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
```
- I have added one more method *create_file_if_not_exists()* which creates necessary files like statefile and processed_files which is required for out script.

```python
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
```

**class tracklivelog**

- the first thing this class does is , retrive the last position of the live log file where we have previously loaded. This is stored in our statefile.txt. 

```python
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
```

Once we recieve the last position , we compare it with the current file size which is again in bytes. 
- If the current file size is less than the last position that means the file has truncated or rotated. In that case the last position is saved back to the state file using the below.
```python
with open(self.filepath, 'r') as f:
    f.seek(self.last_position)  # Start from the last processed position

    current_size = os.path.getsize(self.filepath)
    # print(current_size,self.last_position)

    if current_size < self.last_position:
        # File was rotated or truncated
        print("File was rotated or truncated")
        f.seek(0, os.SEEK_END) 
        self.last_position = f.tell()
```

- If the current file size is greater than last position that means new lines have been added. It reads the new lines , extract required columns and call *load_data()* and save the last position again. 

```python
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
            self.save_last_position()
```

- I am emptying the data list after laoding the data because , if we find new lines again it need not send the previously read lines once again to load_data() . 

- I am also creating hash value for each line that we read to create a unique identifier using the below function

```python
    def create_hash(self,log):
        hash_value = hashlib.sha256(log.encode()).hexdigest()
        return hash_value
```
- the below functions are to save last position and to load data to db

```python
def save_last_position(self):
        with open(self.statefile, 'w') as f:
            f.write(str(self.last_position))

def load_data(self):
    self.load_data_to_db(self.data)

```

**class TrackFolder**

- when we call the constructor, it looks for previoulsy loaded files from our processed_files.json and stores them in a list.

```python
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
```
- once it has the previoulsy loaded files list , it runs the *process_files()* which checks if new files are added. If these new files are not in our previoulsy loaded list and its not a live log files, it is processed.

```python
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
```

Each file is processed using the below functions and send to load the data.

The *read_file()* method reads the file , extracts required columns , creates hash and then sent to load the data.

```python
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
```


**class LogFileHandler**

- This class keeps track of files added in that folder , if yes , it stores the path of new files in the queue.

```python
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
```


**__main__**

- We create the instances of the three classes that we create and pass required args.
```python
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
```

The below code keeps the *detect-file_changes()* method active all the time which tracks the live log file. It also looks for the file_queue() from class LogFileHandler which tracks the folder to see if the queue has recieved any new files path. 

```python
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
```



## Flask Application

**Sample**

Created four functions 

- fetch_transfers()
- get_total_bytes_transferred()
- get_avg_bytes_transferred()
- get_total_acts_by_day()


Each function , will take start date and end date as arguments if given by a user through endpoint if not by default start date would be 2022 - 01 - 01 and end date would be todays date. 

Using these args , every functions runs a sql query to get required data from the mysql server. 

Using the data retrieved from mysql , I format the dataset which includes applying log to the data to make the graoh look better and plotly can easily understand the return the graph to the html template.


```python
def fetch_transfers(st,et):
    # user='%' + user + '%'
    # print(st,et)
    conn,cur=mysql_connect()
    try:
        with open('sql/get_user_transfers.sql') as sql_file:
            user_transfers_sql = sql_file.read()
        cur.execute(user_transfers_sql,[st,et])
    except pymysql.err.InterfaceError as e:
        app.logger.error(f"Database connection issue : {e}")
    except Exception as e:
        app.logger.error(f"An error occured:{e}")

    transfers=[]
    for row in cur:
        line={}
        line['username']=row['username']
        line['transfers']=row['transfers']
        transfers.append(line)

    # print(transfers)

    if transfers is None:
            return "Error fetching data", 500

    transfers_plot = {
        "data": [
            {
                "x": [entry["username"] for entry in transfers],
                "y": [entry["transfers"] for entry in transfers],
                "type": "bar",
                "name": "Transfers",
            }
        ],
        "layout": {
            # "title": "User Transfers",
            "xaxis": {"title": "Username"},
            "yaxis": {"title": "Transfers"},
            "yaxis": dict(type="log")
        },
    }

    return transfers_plot
```

```python
@app.route('/default',methods=['GET'])
def default():
    today=date.today()
    start_date='2023-01-01'

    # print(start_date,today)
    transfers = fetch_transfers(start_date,today)

    bytes=get_total_bytes_transferred(start_date,today)
    avg_bytes=get_avg_bytes_transferred(start_date,today)
    ta=get_total_acts_by_day(start_date,today)

    response_data={
        "transfers":transfers,
        "bytes":bytes,
        "avg_bytes":avg_bytes,
        "ta":ta
    }

    # print(response_data)
    return jsonify(response_data)
```


I have added a startdate and enddate filter for the users to select at the front end.

![Alt text](Images/filter.png)

When the dates are selected and submit button is clicked , it routes to '/update-data' endpoint, which does the same mechanism as '/default' endpoint but this time it sends the user seleted start date and enddate.

```python
@app.route('/update-data', methods=['POST'])
def update_data():
    request_data = request.get_json()
    start_date = request_data['start_date']
    end_date = request_data['end_date']
    # print(start_date,end_date)
           
    transfers = fetch_transfers(start_date,end_date)
    bytes=get_total_bytes_transferred(start_date,end_date)
    avg_bytes=get_avg_bytes_transferred(start_date,end_date)
    ta=get_total_acts_by_day(start_date,end_date)
    # print(transfers)

    if transfers is None or bytes is None or avg_bytes is None and ta is None:
            return "Error fetching data", 500
    
    response_data={
        "transfers":transfers,
        "bytes":bytes,
        "avg_bytes":avg_bytes,
        "ta":ta
    }
    return response_data
```

Run the application

```python
if __name__ == '__main__':
    app.run(debug=True,port=5000)
```


## Front end template script

**Sample**

We have created four functions in the application and each endpoint returns four graphs as a single response in json format. The below script recieves this resonse , and understands the data part and layout part and plots it in the given div. 


```html
<label for="start-date">Start Date:</label>
    <input type="date" id="start-date" name="start-date">
    
    <label for="end-date">End Date:</label>
    <input type="date" id="end-date" name="end-date">
    
    <button id="submit-button">Submit</button>

<div class ='plots'>
    <div class="plot-box">
        <h1>User Transfers</h1>
        <div id="user_transfers"></div>
    </div>

    <div class="plot-box">
        <h1>User Total Bytes Transferred</h1>
        <div id="user_bytes_transfers"></div>
    </div>

    <div class="plot-box">
        <h1>User Avg Bytes Transfers</h1>
        <div id="user_avg_bytes_transfers"></div>
    </div>

    <div class="plot-box">
        <h1>Activities by Day</h1>
        <div id="acts_by_day"></div>
    </div>
</div>

<script>


    $(document).ready(function () {

        $.ajax({
            url: '/default',
            method: 'GET',
            success: function (response) {
                // Render the default Plotly graphs
                console.log(response)
                Plotly.newPlot('user_transfers', response.transfers.data, response.transfers.layout);
                Plotly.newPlot('user_bytes_transfers', response.bytes.data,response.bytes.layout);
                Plotly.newPlot('user_avg_bytes_transfers', response.avg_bytes.data,response.avg_bytes.layout);
                Plotly.newPlot('acts_by_day', response.ta.data,response.ta.layout);
                // Add graphs for graph3 and graph4
            },
            error: function (error) {
                console.error('Error loading default data:', error);
            }
        });


        $('#submit-button').click(function () {
            // Get selected dates
            const startDate = $('#start-date').val();
            const endDate = $('#end-date').val();

            if (!startDate || !endDate) {
                alert('Please select both start and end dates.');
                return;
            }

            // Send data to Flask
            $.ajax({
                url: '/update-data',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ start_date: startDate, end_date: endDate }),
                success: function (response) {
                    // Update Plotly graphs with new data
                    Plotly.newPlot('user_transfers', response.transfers.data, response.transfers.layout);
                Plotly.newPlot('user_bytes_transfers', response.bytes.data,response.bytes.layout);
                Plotly.newPlot('user_avg_bytes_transfers', response.avg_bytes.data,response.avg_bytes.layout);
                Plotly.newPlot('acts_by_day', response.ta.data,response.ta.layout);
                },
                error: function (error) {
                    console.error('Error fetching data:', error);
                }
            });
        });
    });
</script>

```

