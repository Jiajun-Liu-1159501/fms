from curses import delay_output
from decimal import ROUND_HALF_UP, Decimal
import decimal
import re
from flask import Flask, Response, g
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import session
from datetime import date, datetime, timedelta
import connect
from typing import Any, Dict, Generic, List, TypeVar, Callable, Tuple
from mysql.connector import pooling, cursor


app = Flask(__name__)
app.secret_key = 'COMP636 S2'

start_date = datetime(2024,10,29)
pasture_growth_rate = 65    #kg DM/ha/day
stock_consumption_rate = 14 #kg DM/animal/day

def _init_connection_pool() -> pooling.MySQLConnectionPool:
    """
    init database connection pool useing args in connect.py given,
    using single database conection in mutiple threads web application is not thread safey
    """
    db_config: Dict[str, Any] = {
        "host": connect.dbhost,
        "port": connect.dbport,
        "user": connect.dbuser,
        "password": connect.dbpass,
        "database": connect.dbname,
        "autocommit": True
    }
    return pooling.MySQLConnectionPool(pool_name = "db_conn_pool", pool_size = 3, **db_config) # the max db connetion in pool is setted to 3

connection_pool: pooling.MySQLConnectionPool = _init_connection_pool() #use pooled objects instead single connection instance

@app.before_request
def do_before() -> None:
    """
    bind a db session to a request thread using arg g befor handling request
    """
    connection: pooling.PooledMySQLConnection = connection_pool.get_connection() # borrow a connection from a pool
    g.db_connection = connection

@app.after_request
def do_after(response: Response) -> None:
    """
    return a db session to connection pool after request
    """
    connection: pooling.PooledMySQLConnection = g.db_connection
    connection.close() # close() method will return the connection to the pool, not closing a connection
    return response

@app.route("/")
def home():
    if 'curr_date' not in session:
        session.update({'curr_date': start_date})
    data: Dict[str, Any] = {"page": "home"} 
    return render_template("home.html", data = data)

@app.route("/clear-date")
def clear_date():
    """
    Clear session['curr_date']. Removes 'curr_date' from session dictionary.
    """
    session.pop('curr_date')
    return redirect(url_for('paddocks'))  

@app.route("/reset-date")
def reset_date():
    """
    Reset session['curr_date'] to the project start_date value.
    """
    session.update({'curr_date': start_date})
    return redirect(url_for('paddocks'))  

@app.get("/mobs")
def mobs() -> str:
    """
    List the mob details (excludes the stock in each mob).
    """
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    query: str = "SELECT a.id, a.name as mob_name, b.name as paddock_name FROM mobs a LEFT JOIN paddocks b on a.paddock_id = b.id ORDER BY a.name ASC;"
    cur.execute(query)        
    mobs: List[Dict[str, Any]] = cur.fetchall()   
    data: Dict[str, Any] = {"page": "mobs", "mobs": mobs}      
    return render_template("mobs.html", data = data)

@app.get("/stocks")
def stocks() -> str:
    """
    List the mob details (excludes the stock in each mob).
    """
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    mob_query: str = "SELECT a.id as mob_id, a.name as mob_name, a.paddock_id, b.name as paddock_name, b.area, b.dm_per_ha, b.total_dm FROM mobs a LEFT JOIN paddocks b ON a.paddock_id = b.id ORDER BY a.name;"
    cur.execute(mob_query)
    mob_dict: List[Dict[str, Any]] = cur.fetchall()
    stock_query: str = "SELECT * FROM stock ORDER BY id ASC;"
    cur.execute(stock_query)
    stock_dict: List[Dict[str, Any]] = cur.fetchall()
    grouped_stocks: Dict[str, List[Dict[str, Any]]] = {}
    for item in stock_dict:
        grouped_stocks.setdefault(item.get("mob_id"), []).append(item)
    for mob in mob_dict:
        stocks = grouped_stocks.get(mob.get("mob_id"))
        mob.setdefault("stocks", stocks)
    data: Dict[str, Any] = {"page": "stocks", "mob_dict": mob_dict}    
    return render_template("stocks.html", data = data)

@app.get("/paddocks")
def paddocks() -> str:
    """
    List paddock details.
    """
    g.page = "paddocks"
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    query: str = "SELECT a.*, b.name as mob_name, COUNT(c.id) as sotck_num FROM paddocks a LEFT JOIN mobs b ON a.id = b.paddock_id LEFT JOIN stock c ON c.mob_id = b.id GROUP BY a.id ORDER BY a.name ASC;"
    cur.execute(query)
    paddocks: List[Dict[str. Any]] = cur.fetchall()
    data: Dict[str, Any] = {"page": g.page, "paddocks": paddocks}
    return render_template("paddocks.html", data = data)

@app.post("/paddcoks/add")
def add_paddocks() -> str:
    """
    edit a paddock
    """
    g.page = "paddocks"
    paddock_name: str = request.form.get("paddock_name")
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    paddock_area: Decimal = Decimal(request.form.get("paddock_area"))
    paddock_dh: Decimal = Decimal(request.form.get("paddock_dm"))
    update_statement = "INSERT INTO paddocks (name, area, dm_per_ha, total_dm) VALUES (%s, %s, %s, %s);"
    cur.execute(update_statement, [paddock_name, paddock_area, paddock_dh, _calculate_total_dm(paddock_area, paddock_dh)])
    return redirect(url_for("paddocks"))

@app.post("/paddcoks/edit")
def edit_paddocks() -> str:
    """
    edit a paddock
    """
    g.page = "paddocks"
    paddock_id: int = int(request.form.get("paddock_id"))
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    paddock_valid_query: str = "SELECT COUNT(1) as count FROM paddocks WHERE id = %s;"   # make sure two paddocks exist
    cur.execute(paddock_valid_query, [paddock_id])
    if cur.fetchone()['count'] != 1:
        raise Exception("invalid paddock id submitted")
    paddock_name: str = request.form.get("paddock_name")
    paddock_area: Decimal = Decimal(request.form.get("paddock_area"))
    paddock_dh: Decimal = Decimal(request.form.get("paddock_dm"))
    update_statement = "UPDATE paddocks SET name = %s, area = %s, dm_per_ha = %s, total_dm = %s WHERE id = %s;"
    cur.execute(update_statement, [paddock_name, paddock_area, paddock_dh, _calculate_total_dm(paddock_area, paddock_dh), paddock_id])
    return redirect(url_for("paddocks"))

@app.post("/paddcoks/move")
def move_paddocks() -> str:
    """
    move between different paddocks
    """
    g.page = "paddocks"
    params: List[int] = [int(request.form.get("target_id")), int(request.form.get("source_id"))]
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    paddock_valid_query: str = "SELECT COUNT(1) as count FROM paddocks WHERE id IN (%s , %s);"   # make sure two paddocks exist
    cur.execute(paddock_valid_query, params)
    if cur.fetchone()['count'] != 2:
        raise Exception("invalid paddock id submitted")
    update_statement: str = "UPDATE mobs SET paddock_id = %s WHERE paddock_id = %s;"
    cur.execute(update_statement, params)
    return redirect(url_for("paddocks"))
    
@app.errorhandler(Exception)
def unknown_error_handler(exp: Exception) -> str:
    """
    handle global exception, in this case catch base exception only and return the same error page
    """
    print(exp)
    data = {"page": g.page}
    return render_template("error.html", data = data)

def _calculate_total_dm(area: Decimal, dh: Decimal) -> Decimal:
    total_dm: Decimal = area * dh
    return total_dm.quantize(Decimal('0.0'), rounding = ROUND_HALF_UP)

if __name__ == "__main__":
    app.run()