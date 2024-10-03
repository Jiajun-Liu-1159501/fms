from threading import Lock
from flask import Flask, g
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import session
from datetime import date, datetime, timedelta
import mysql.connector, connect
from typing import Any, Dict, Generic, TypeVar, Callable
from mysql.connector import pooling, cursor


app = Flask(__name__)
app.secret_key = 'COMP636 S2'

start_date = datetime(2024,10,29)
pasture_growth_rate = 65    #kg DM/ha/day
stock_consumption_rate = 14 #kg DM/animal/day

def _init_connection_pool() -> pooling.MySQLConnectionPool:
    """
    init database connection pool useing args in connect.py given,
    using single database conection in mutiple thread web application is not thread safey
    """
    db_config: Dict[str, Any] = {
        "host": connect.dbhost,
        "port": connect.dbport,
        "user": connect.dbuser,
        "password": connect.dbpass,
        "database": connect.dbname,
        "autocommit": True
    }
    return pooling.MySQLConnectionPool(pool_name = "db_conn_pool", pool_size = 3, **db_config)

connection_pool: pooling.MySQLConnectionPool = _init_connection_pool() #use pooled objects instead single connection instance

@app.before_request
def do_before() -> None:
    """
    bind a db session to a request thread using arg g befor handling
    """
    connection: pooling.PooledMySQLConnection = connection_pool.get_connection()
    g.db_connection = connection

@app.after_request
def do_after(response) -> None:
    """
    return a db session to connection pool after request
    """
    connection: pooling.PooledMySQLConnection = g.db_connection
    connection.close() # close method will return the connection to the pool, not closing a connection
    return response

@app.route("/")
def home():
    if 'curr_date' not in session:
        session.update({'curr_date': start_date})
    return render_template("home.html")

@app.route("/clear-date")
def clear_date():
    """Clear session['curr_date']. Removes 'curr_date' from session dictionary."""
    session.pop('curr_date')
    return redirect(url_for('paddocks'))  

@app.route("/reset-date")
def reset_date():
    """Reset session['curr_date'] to the project start_date value."""
    session.update({'curr_date': start_date})
    return redirect(url_for('paddocks'))  

@app.route("/mobs")
def mobs():
    """List the mob details (excludes the stock in each mob)."""
    connection: pooling.PooledMySQLConnection = g.db_connection
    cur: cursor.MySQLCursor = connection.cursor(dictionary = True, buffered = False)
    cur.execute("SELECT id, name FROM mobs;")        
    mobs = cur.fetchall()        
    return render_template("mobs.html", mobs = mobs)  

@app.route("/paddocks")
def paddocks():
    """List paddock details."""
    return render_template("paddocks.html")  

if __name__ == "__main__":
    app.run()