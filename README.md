## FMS

#### Design

First of all, I tried to rewirte the method of acquire a db connection, using a connection pool instead. The connection limits the max database connections that the web applicaton can acquire. Each request thread will try to obtain a connection from a blocking queue, if the queue is empty(all connections in connection pool are in use), the request thread will wait until other thread returns a conection to the pool.

Next, there will be 3 main pages in this web application:

- mob page: /mobs
- paddock page: /paddocks
- stock page: /stocks

Each main page corresponds to a URL using GET method. No more functions in page `mob` and `stock`, just select their data from database using join statement, very easy.

In the paddock page, there will be 4 functions

- add paddock
- edit paddock
- move paddock
- move to next day

For the function `add paddock`, we don't need to fetch any data form backend server, so use the Modal compnent, when the add button clicked, the Modal window will pop up. Then the form will submit using http POST, or cancel this Modal.

For the function `edit paddock`, we need to identity which row is selected for editing, so I decided to build buttons into the table to edit each row. Use `onclick` method to get the selected row and its data, then pop up a Modal window, init the values of the compnents in the Modal. Then the form. will submit using http POST, or cancel this Modal.

For the function `move paddock`, the most troublesome part is that I need to know whether there is an available paddock. If there is no available paddock, the move operation will not be completed. So I set the entry button to an empty paddock, if there is one. In this case， I only need to detect if there is a mob name in this paddock, if not, this paddock is available, the move-in button will display. After the Move-In button is clicked, the form will request a new page using argument `target_id`, this is the target paddock in the next step. In the new page, Each row will implicitly contain a `target_id`, which will wrapped in a form. When the move-out button is clicked, the source paddock is selected, the form will submit `source_id` and `target_id` to the backend server. When the operation is successful, the submit URL will redirect to page `paddock`.

For the function `move to next day`, in normal way, we need to update the date first, this needs one I/O to database, then query all the paddocks with their stock number into VM heap, one more I/O needed, finally recalculate the consumption of each paddock and update the new values into database, this step need at least antoher one I/O(depends on using batch operation or not). Therefore at least 3 I/O are needed in normal way. However, if I pass the consumption rate as an argument of a sql statement, then calculate the new values in MySQL using two temp tables, we can merge the last twice I/O, therefore only 2 I/O are needed if I calculate them in database.


#### Image Source

1. Homepage: https://huaban.com/pins/1589034720 


#### Database questions
1. What SQL statement creates the mobs table and defines its fields/columns? (Copy
and paste the relevant lines of SQL.)

    ```SQL
    CREATE TABLE mobs (
        id int NOT NULL AUTO_INCREMENT,
        name varchar(50) DEFAULT NULL,
        paddock_id int not null,
        PRIMARY KEY (id),
        UNIQUE INDEX paddock_idx (paddock_id),	-- Ensures that paddock_id is unique
        CONSTRAINT fk_paddock
            FOREIGN KEY (paddock_id)
            REFERENCES paddocks(id)
            ON DELETE NO ACTION
            ON UPDATE NO ACTION
    );
    ```

2. Which lines of SQL script sets up the relationship between the mobs and paddocks
tables?

    ```SQL
    CREATE TABLE mobs (
        ...
        paddock_id int not null,
        ...
        CONSTRAINT fk_paddock
            FOREIGN KEY (paddock_id)
            REFERENCES paddocks(id)
            ON DELETE NO ACTION
            ON UPDATE NO ACTION
    );
    ```

3. The current FMS only works for one farm. Write SQL script to create a new table
called farms, which includes a unique farm ID, the farm name, an optional short
description and the owner’s name. The ID can be added automatically by the
database. (Relationships to other tables not required.)

    ```SQL
    CREATE TABLE farms (
        id int NOT NULL AUTO_INCREMENT,
        farm_name varchar(50) DEFAULT NULL,
        owner_name varchar(50) DEFAULT NULL,
        desc varchar(255) DEFAULT NULL,
        PRIMARY KEY (id)
    );
    ```

4. Write an SQL statement to add details for an example farm to your new farms table, which would be suitable to include in your web application for the users to add farms in a future version. (Type in actual values, don’t use %s markers.)

    ```SQL
    INSERT INTO farms ('farm_name', 'owner_name', 'desc') VALUES ('mock_farm_name', 'mock_owner_name', 'mock_desc');
    ```

5. What changes would you need to make to other tables to incorporate the new farms
table? (Describe the changes. SQL script not required.)

    add a column *`farm_id`* in table *`paddocks`*, the SQL script is as below:

    ```SQL
    ALTER TABLE paddocks ADD farm_id int NOT NULL;
    ```
