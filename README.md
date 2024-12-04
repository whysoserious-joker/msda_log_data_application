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
- Folder Monitoring: Detect and process new folders added to a specified directory (logs).d.

**Challenges**

- Duplicate rows shouldnt be processed 
- if the tracker script fails at some point it should pick up from where it left
- we don't have a unique identifier for a log entry , because timestamp has milliseconds and there might be duplicates even at millisecond.



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

