from decimal import ROUND_HALF_UP, Decimal
from flask import Flask, Response, flash, g
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from datetime import date
import connect, logging, uuid
from typing import Any, Dict, List
from mysql.connector import pooling, cursor
from pathlib import Path


app = Flask(__name__)
app.secret_key = 'COMP636 S2'

pasture_growth_rate = 65    #kg DM/ha/day
stock_consumption_rate = 14 #kg DM/animal/day

def _init_connection_pool() -> pooling.MySQLConnectionPool:
    """
    init database connection pool using args in connect.py given,
    using single database conection in mutiple threads web application environment is not thread safey
    """
    db_config: Dict[str, Any] = {
        "host": connect.dbhost,
        "port": connect.dbport,
        "user": connect.dbuser,
        "password": connect.dbpass,
        "database": connect.dbname,
        "autocommit": True
    }
    return pooling.MySQLConnectionPool(pool_name = "db_conn_pool", pool_size = 3, **db_config) # set the max db connetion to 3

connection_pool: pooling.MySQLConnectionPool = _init_connection_pool() #use pooled objects instead single connection instance

@app.before_request
def do_before() -> None:
    """
    bind a db session to a request thread using arg g befor handling request
    """
    g.trace_id = str(uuid.uuid4())  # gen a uuid as trace_id for every request
    app.logger.info(f"Request path: {request.path}")
    if request.args: app.logger.info(f"parameters: {request.args}") # print url args in request
    if request.form: app.logger.info(f"body: {request.form}")   # print body args in request if method is POST[application/x-www-form-urlencoded]
    connection: pooling.PooledMySQLConnection = connection_pool.get_connection() # borrow a connection from a pool
    g.db_connection = connection

@app.after_request
def do_after(response: Response) -> None:
    """
    return a db session to connection pool after request
    """
    connection: pooling.PooledMySQLConnection = g.db_connection
    connection.close() # close() method will return the connection to the pool, not closing a connection
    app.logger.info(f"Response status: {response.status}")
    return response

def get_date(cursor: cursor.MySQLCursor) -> date:
    """
    rewrite the get date method using request binded cursor
    """
    cursor.execute("SELECT curr_date FROM curr_date;") 
    curr_date: date = cursor.fetchone()['curr_date'] 
    return curr_date

@app.get("/")
def home() -> str:
    """
    home page
    """
    g.page = "home" # every g.page param is used for identify the current page in errorhanlder, then can jump back from error page
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    data: Dict[str, Any] = {"page": g.page, "curr_date": get_date(cur)} # the 'page' param in data is used for holding the menu item selection
    return render_template("home.html", data = data)

@app.get("/mobs")
def mobs() -> str:
    """
    List the mob details (excludes the stock in each mob).
    """
    g.page = "mobs"
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    cur.execute("SELECT a.id, a.name as mob_name, b.name as paddock_name FROM mobs a LEFT JOIN paddocks b on a.paddock_id = b.id ORDER BY a.name ASC;")
    mobs: List[Dict[str, Any]] = cur.fetchall()   
    data: Dict[str, Any] = {"page": g.page, "curr_date": get_date(cur), "mobs": mobs}      
    return render_template("mobs.html", data = data)

@app.get("/stocks")
def stocks() -> str:
    """
    List the mob details (excludes the stock in each mob).
    """
    g.page = "stocks"
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    current_date: date = get_date(cur)
    mob_query: str = "SELECT a.id as mob_id, a.name as mob_name, a.paddock_id, b.name as paddock_name, b.area, b.dm_per_ha, b.total_dm FROM mobs a LEFT JOIN paddocks b ON a.paddock_id = b.id ORDER BY a.name;"
    cur.execute(mob_query)
    mob_dict: List[Dict[str, Any]] = cur.fetchall()     # get the mobs with their paddcok infos first use join query
    stock_query: str = "SELECT * FROM stock ORDER BY id ASC;"
    cur.execute(stock_query)
    stock_dict: List[Dict[str, Any]] = cur.fetchall()   # get all stocks then, grouping them in memory not in database
    grouped_stocks: Dict[str, List[Dict[str, Any]]] = {}
    for item in stock_dict:
        grouped_stocks.setdefault(item.get("mob_id"), []).append(item)
    for mob in mob_dict:
        stocks: List[Dict[str, Any]] = grouped_stocks.get(mob.get("mob_id"))    # set groupped stocks to mapped mob
        total_sum: Decimal = Decimal(0.00)      # calculate total_weight and age in the same loop
        for stock in stocks:
            total_sum += Decimal(stock.get("weight"))
            stock.setdefault("age", _calculate_age(stock.get("dob"), current_date))
        mob.setdefault("stocks", stocks)
        mob.setdefault("average_weight", (total_sum / len(stocks)).quantize(Decimal('0.00'), ROUND_HALF_UP))
    data: Dict[str, Any] = {"page": g.page, "curr_date": current_date, "mob_dict": mob_dict}    
    return render_template("stocks.html", data = data)

def _calculate_age(date_of_birth: date, current_date: date) -> int:
    """
    calculate year difference, accurate to the day
    """
    age = current_date.year - date_of_birth.year
    if (current_date.month, current_date.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age

@app.get("/paddocks")
def paddocks() -> str:
    """
    List paddock details.
    """
    g.page = "paddocks"
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    paddocks: List[Dict[str. Any]] = _fetch_paddock_list(cur)
    data: Dict[str, Any] = {"page": g.page, "curr_date": get_date(cur), "paddocks": paddocks}
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
    cur.execute(update_statement, [paddock_name, paddock_area, paddock_dh, (paddock_area * paddock_dh).quantize(Decimal('0.0'), rounding = ROUND_HALF_UP)])
    flash(f"Paddock added successfully!", "success")
    return redirect(url_for("paddocks"))

@app.post("/paddcoks/edit")
def edit_paddocks() -> str:
    """
    edit a paddock
    """
    g.page = "paddocks"
    paddock_id: int = int(request.form.get("paddock_id"))
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    paddock_valid_query: str = "SELECT COUNT(1) as count FROM paddocks WHERE id = %s;"   # make sure the paddocks exist use a COUNT query
    cur.execute(paddock_valid_query, [paddock_id])
    if cur.fetchone()['count'] != 1:
        raise Exception("invalid paddock id submitted") # no record then raise an exception, the exception will be handled in errorhanlder
    paddock_name: str = request.form.get("paddock_name")
    paddock_area: Decimal = Decimal(request.form.get("paddock_area"))
    paddock_dh: Decimal = Decimal(request.form.get("paddock_dm"))
    update_statement = "UPDATE paddocks SET name = %s, area = %s, dm_per_ha = %s, total_dm = %s WHERE id = %s;"
    cur.execute(update_statement, [paddock_name, paddock_area, paddock_dh, (paddock_area * paddock_dh).quantize(Decimal('0.0'), rounding = ROUND_HALF_UP), paddock_id])
    flash(f"Paddock edited successfully!", "success")
    return redirect(url_for("paddocks"))

@app.get("/move")
def move_page() -> str:
    g.page = "paddocks"
    target_id: int = request.args.get('target_id', type=int)
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    paddocks: List[Dict[str. Any]] = _fetch_paddock_list(cur)
    for item in paddocks:
        item.setdefault("target_id", target_id)
    data: Dict[str, Any] = {"page": g.page, "curr_date": get_date(cur), "paddocks": paddocks}
    return render_template("move.html", data = data)

def _fetch_paddock_list(cur: cursor.MySQLCursor) -> List[Dict[str, Any]]:
    """
    Both move page and paddock page will use this SQL query, so make fetch_paddock_list as a private method
    """
    cur.execute("SELECT a.*, b.name as mob_name, COUNT(c.id) as sotck_num FROM paddocks a LEFT JOIN mobs b ON a.id = b.paddock_id LEFT JOIN stock c ON c.mob_id = b.id GROUP BY a.id ORDER BY a.name ASC;")
    return cur.fetchall()

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
    paddock_empty_query: str = "SELECT COUNT(1) as count FROM mobs WHERE paddock_id = %s;"   # check target paddock is empty
    cur.execute(paddock_empty_query, [params[0]])
    if cur.fetchone()['count'] > 0:
        raise Exception("this paddock is not empty")
    update_statement: str = "UPDATE mobs SET paddock_id = %s WHERE paddock_id = %s;"
    cur.execute(update_statement, params)
    flash(f"Paddock moved successfully!", "success")
    return redirect(url_for("paddocks"))

@app.post("/paddcoks/next_day")
def move_next_day() -> str:
    """
    Move to next day, update table curr_date and table paddock, recalculate Total DM and DM/HA
    """
    g.page = "paddocks"
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    update_date_statement: str = "UPDATE curr_date SET curr_date = DATE_ADD(curr_date, INTERVAL 1 DAY);" #update curr_date table immidiertly using build-in SQL functon
    cur.execute(update_date_statement)
    update_paddock_statement: str = """ 
        UPDATE paddocks e JOIN (
	        SELECT d.paddock_id as paddock_id, ROUND(d.paddock_area * %s - d.sotck_num * %s, 2) as consumption FROM (
		        SELECT a.id as paddock_id, a.area as paddock_area, COUNT(c.id) as sotck_num FROM paddocks a LEFT JOIN mobs b ON a.id = b.paddock_id LEFT JOIN stock c ON c.mob_id = b.id GROUP BY a.id
	        ) as d
        ) as f ON e.id = f.paddock_id SET e.dm_per_ha = ROUND((e.total_dm + f.consumption) / e.area, 2), e.total_dm = e.total_dm + f.consumption;
    """ # all the values to be updated can be calculated is MySQL server, no need to calculate in memory. 
    # Directly executing this statement only requires one I/O, select first then update need twice.
    cur.execute(update_paddock_statement, [pasture_growth_rate, stock_consumption_rate])
    flash(f"Date moved successfully!", "success")
    return redirect(url_for("paddocks"))

@app.post("/paddocks/reset")
def reset() -> str:
    """
    Reset data to original state.
    """
    g.page = "paddocks"
    cur: cursor.MySQLCursor = g.db_connection.cursor(dictionary = True, buffered = False)
    THIS_FOLDER = Path(__file__).parent.resolve()
    with open(THIS_FOLDER / 'fms-reset.sql', 'r') as f:
        mqstr: str = f.read()
        for qstr in mqstr.split(";"):
            cur.execute(qstr)
    flash(f"Date reseted successfully!", "success")
    return redirect(url_for('paddocks'))
    
@app.errorhandler(Exception)
def unknown_error_handler(exp: Exception) -> str:
    """
    handle global exception, in this case catch base exception only and return the same error page
    """
    app.logger.error(f"Error : {exp}")
    data = {"page": getattr(g, "page", "home")}
    return render_template("error.html", data = data)

class TraceIdFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = getattr(g, "trace_id", "N/A") # hold the trace_id in logger record
        return True

if __name__ == "__main__":
    loggers: List[logging.Logger] = [app.logger, logging.getLogger('werkzeug')] # remove default logger
    for logger in loggers:
        if logger.hasHandlers():
            logger.handlers.clear()
    handler: logging.StreamHandler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: [Trace ID: %(trace_id)s] %(message)s'))
    handler.addFilter(TraceIdFilter())
    app.logger.addHandler(handler)  # add customer logger with trace_id pre request
    app.logger.setLevel(logging.DEBUG)
    app.run()