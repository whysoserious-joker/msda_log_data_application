from flask import Flask
from flask import render_template
from flask import request,session, redirect, url_for, send_from_directory,make_response ,jsonify
from flask_session import Session
import pandas as pd
from datetime import timedelta,datetime, date
import datetime
import time
import json,os
import pymysql
import prebuilt_loggers as prebuilt_loggers
import plotly
import plotly.graph_objects as go


app_log = prebuilt_loggers.filesize_logger('logs/app.log')
#create Flask app instance
app = Flask(__name__,static_url_path='')
application = app

app.config['SESSION_TYPE'] = 'filesystem'

sess = Session()
sess.init_app(app)

# endpoint route for static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

def mysql_connect():
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'password',
        'database': 'msda_log',
        'autocommit':True
    }
    try:
        conn=pymysql.connect(**db_config)
        cur = conn.cursor(pymysql.cursors.DictCursor)
        return conn,cur
    except pymysql.MySQLError as e:
        app_log.error(f"Database connection failed: {str(e)}")
        return None, None

def get_usernames():
    conn,cur=mysql_connect()
    try:
        usernames_sql=open('sql/get_usernames.sql').read()
        cur.execute(usernames_sql)
    except pymysql.err.InterfaceError as e:
        app.logger.error(f"Database connection issue : {e}")
    except Exception as e:
        app.logger.error(f"An error occured:{e}")

    usernames=['All']
    for row in cur:
        usernames.append(row['username'])
    
    return usernames

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

def get_ips_per_user():
    conn,cur=mysql_connect()
    try:
        user_ips_sql=open('sql/get_ips_per_user.sql').read()
        cur.execute(user_ips_sql)
    except pymysql.err.InterfaceError as e:
        app.logger.error(f"Database connection issue : {e}")
    except Exception as e:
        app.logger.error(f"An error occured:{e}")

    ips=[]
    for row in cur:
        line={}
        line['username']=row['username']
        line['ips']=row['ips']
        ips.append(line)
    return ips

def get_total_bytes_transferred(st,et):
    conn,cur=mysql_connect()
    try:
        user_bytes_sql=open('sql/get_bytes_transferred_by_user.sql').read()
        cur.execute(user_bytes_sql,[st,et])
    except pymysql.err.InterfaceError as e:
        app.logger.error(f"Database connection issue : {e}")
    except Exception as e:
        app.logger.error(f"An error occured:{e}")

    bytes=[]
    for row in cur:
        line={}
        line['username']=row['username']
        line['sender']=row['sender']
        line['bytes_transferred']=row['bytes_transfered']
        bytes.append(line)

    if bytes is None:
            return "Error fetching data", 500
    senders = list(set(entry['sender'] for entry in bytes))  # Get unique senders

    # Create a trace for each sender
    data_traces = []
    for sender in senders:
        data_traces.append({
            "x": [entry["username"] for entry in bytes if entry["sender"] == sender],  
            "y": [entry["bytes_transferred"] for entry in bytes if entry["sender"] == sender],  
            "type": "bar",  
            "name": sender,  # Use the sender name for this trace
            "text": [entry["bytes_transferred"] for entry in bytes if entry["sender"] == sender],  
            "hoverinfo": "x+y+text",  
        })

    # Define the plot
    bytes_plot = {
        "data": data_traces,
        "layout": {
            # "title": "Bytes Transferred",
            "xaxis": {"title": "Username"},
            "yaxis": {"title": "Bytes", "type": "log"},  # Use log scale for the Y-axis
            "barmode": "group",  # Group bars by sender
        },
    }


    return bytes_plot

def get_avg_bytes_transferred(st,et):
    conn,cur=mysql_connect()
    try:
        user_ips_sql=open('sql/get_avg_bytesize_transferred.sql').read()
        cur.execute(user_ips_sql,[st,et])
    except pymysql.err.InterfaceError as e:
        app.logger.error(f"Database connection issue : {e}")
    except Exception as e:
        app.logger.error(f"An error occured:{e}")

    avg_bytes=[]
    for row in cur:
        line={}
        line['username']=row['username']
        line['avg_bytes']=row['avg_transfer_byte_size']
        avg_bytes.append(line)

    if avg_bytes is None:
            return "Error fetching data", 500

    avg_bytes_plot = {
        "data": [
            {
                "x": [entry["username"] for entry in avg_bytes],
                "y": [entry["avg_bytes"] for entry in avg_bytes],
                "type": "bar",
                "name": "Avg byte Transfers",
            }
        ],
        "layout": {
            # "title": "User Transfers",
            "xaxis": {"title": "Username"},
            "yaxis": {"title": "Avg Transfers","type":"log"},
        },
    }

    return avg_bytes_plot

def get_total_acts_by_day(st,et):
    conn,cur=mysql_connect()
    try:
        total_acts_sql=open('sql/total_acts_by_day.sql').read()
        cur.execute(total_acts_sql,[st,et])
    except pymysql.err.InterfaceError as e:
        app.logger.error(f"Database connection issue : {e}")
    except Exception as e:
        app.logger.error(f"An error occured:{e}")

    ta=[]
    for row in cur:
        line={}
        line['date']=row['date']
        line['total_acts']=row['total_acts']
        ta.append(line)
    
    if ta is None:
            return "Error fetching data", 500

    ta_plot = {
        "data": [
            {
                "x": [entry["date"] for entry in ta],
                "y": [entry["total_acts"] for entry in ta],
                "type": "scatter",
                "name": "Daily activities",
                 "mode": "lines+markers",
            }
        ],
        "layout": {
            # "title": "User Transfers",
            "xaxis": {"title": "date"},
            "yaxis": {"title": "activities_count"},
        },
    }
    return ta_plot

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

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


    # ips=get_ips_per_user()
    # bytes=get_total_bytes_transferred()
    # avg_bytes=get_avg_bytes_transferred()
    # ta=get_total_acts_by_day()


    # #################
    # # Prepare data for Plotly
    # usernames = list(set(item['username'] for item in bytes))
    # senders = list(set(item['sender'] for item in bytes))
   
    # total_transfers = [
    #     sum(t['transfers'] for t in transfers if t['username'] == username) for username in usernames
    # ]
    # total_fig = go.Figure(data=[
    #     go.Bar(x=usernames, y=total_transfers, marker_color="lightseagreen")
    # ])
    # total_fig.update_layout(
    #     # title="Total Transfers by User",
    #     xaxis_title="Usernames",
    #     yaxis_title="Total Transfers",
    #     yaxis=dict(type="log")
    # )
    # total_chart_json = json.dumps(total_fig, cls=plotly.utils.PlotlyJSONEncoder)


    # ########################################
    # # Create traces for each sender
    # traces = []
    # for sender in senders:
    #     sender_data = [next((t['bytes_transfered'] for t in bytes if t['username'] == username and t['sender'] == sender), 0) for username in usernames]
    #     traces.append(go.Bar(name=sender, x=usernames, y=sender_data))

    # # Create the figure
    # fig = go.Figure(data=traces)
    # fig.update_layout(
    #     # title="Transfers by User by Sender",
    #     xaxis_title="Usernames",
    #     yaxis_title="Number of Transfers",
    #     barmode="group",
    #     yaxis=dict(type="log")
    # )
    # # Convert Plotly figure to JSON for embedding
    # graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    # ########################################
    # # Prepare data for Plotly
    # usernames = list(set(item['username'] for item in avg_bytes))

   
    # avg_transfers = [
    #     sum(t['avg_bytes'] for t in avg_bytes if t['username'] == username) for username in usernames
    # ]
    # print(avg_transfers)
    # avg_fig = go.Figure(data=[
    #     go.Bar(x=usernames, y=avg_transfers, marker_color="lightskyblue")
    # ])
    # avg_fig.update_layout(
    #     # title="Avg Transfers by User",
    #     xaxis_title="Usernames",
    #     yaxis_title="Avg Transfers"
    # )
    # avg_chart_json = json.dumps(avg_fig, cls=plotly.utils.PlotlyJSONEncoder)

    # ##############################################

    # dfta = pd.DataFrame(ta)
    # dfta['date'] = pd.to_datetime(dfta['date'])
    # aggregated = dfta.groupby('date')['total_acts'].sum().reset_index()

    # line_fig = go.Figure()
    # line_fig.add_trace(go.Scatter(
    #     x=aggregated['date'], 
    #     y=aggregated['total_acts'], 
    #     mode='lines+markers', 
    #     name='activities'
    # ))

    # line_fig.update_layout(
    #     # title="Activities Over Time",
    #     xaxis_title="date",
    #     yaxis_title="Number of Acts",
    # )

    # line_chart_json = json.dumps(line_fig, cls=plotly.utils.PlotlyJSONEncoder)



    # return render_template('dashboard.html',transfers=transfers,graph_json=graph_json, total_chart_json=total_chart_json,avg_chart_json=avg_chart_json,line_chart_json=line_chart_json)


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


if __name__ == '__main__':
    app.run(debug=True,port=5000)