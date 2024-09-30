## FMS





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

    add a column 'farm_id' in table paddocks, the SQL script is as below:

    ```SQL
    ALTER TABLE paddocks ADD farm_id int NOT NULL;
    ```