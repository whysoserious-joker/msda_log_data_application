## Setup you loader

I assume that you have a folder where all the logs data files are stored , lets say the folder name is **logs**.

To get started with setting up your loader , you need to setup your **config.yml** file.

```yml
db:
  username: 'root'
  password: 'password'
  hostname: 'localhost'
  port: 3306
  database_name: 'msda_log'
  table_name: 'logdata'

livefile:
  filename: 'sftpgo.log'
  statefile: 'statefile.txt'

folder:
  path: '../logs'
  processed_files: 'processed_logs.json'
```

**db**

- this section holds your data which is needed to connect to your database

**livefile**

- filename: this is your live log file name. This file collects log data live.
- statefile: this file is used to keep track of the last position of the live log file was read which means lets say the live log file has 10 lines and in next 5 min a new log data was captured , this statefile keeps track what was the last position the lines were read from . Even if the loader script fails and meanwhile logs were collected , it will still be read later because of this statefile keep track of last read position

**folder**

- path: this is your folder where logs data files are captured
- processed_files: this file is used to keep track of previously loaded log filenames and time.


## run the loader script 'logtrack.py' 

Once you setup your config file , all you need to do is run your tracker/loader script.
This script , by default does the below things:

- checks if the table exists in your database , if not a table will be created along with its index.
- checks if the statefile and processed_files are created , if not it creates them.
- it tracks if there are any new log lines are added in live log file , if added , it reads them and will be loaded to the table along with the timestamp.
- it tracks the log folder if there are any new log files are added, if yes , it reads them and loads to the database table.
- since we are doing insert ignore you dont have to worry about duplicate logs loading.


## What if you want to load all logfiles and live log file to a new table or the same table if table got dropped.

you just need to do one of the below 

- delete statefile and processed_file and re run the tracker script

 or 

- empty your processed_file and open your statefile and enter 0 at the beginning of the file which means to tell the script to start reading the live log file from the beginning.






