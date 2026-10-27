# **PROJECT OVERVIEW:**

This project is done to build a local data engineering pipeline to test synthetically produced transaction and entity data. It validates the incoming records (using Pydantic contracts) by re-routing the invalid records to the Dead Letter Queue(DLQ) and loads the valid record into the DuckDB database (Bronze Layer). In the Silver Layer, the Bronze data is now cleaned and the relationships between entities and transactions are checked for validity. The Gold Star Schema is then built with the valid records in order to have a clean dataset and executes SQL queries on them.

## **1.**     **SETUP:**

Prerequisites: Python 3.10 or later versions

python -m venv .venv

.venv\Scripts\activate

python -m pip install --upgrade pip

pip install -r requirements.txt

## **2.**     **DATA GENERATION:**

Synthetic data is generated using Python. The generator is made to create two files:

i)                entities.csv : A .csv file containing entity/customer information (1120 records - 1000 valid, 60 with malformed email addresses, 60 duplicates)

-        entity_id

-        first_name

-        last_name

-        contact_email

-        registration_date

-        region

ii)              transactions.json: A .json file containing the transactions (5000 records - 50 negative amounts, 50 missing/null IDs, 50 invalid currencies)

-        transaction_id

-        entity_id

-        category

-        transaction_amount

-        currency

-        timestamp

The code contains a predefined list of names, regions and other values. Python will randomly select values from them and construct the entities.

The generator code is made in such a way that duplicates/malformed addresses/missing values or other invalid data rows are also produced.

## **3.**     **PIPELINE EXECUTION:**

The run_pipeline.py file runs the file and provides the outputs of the stages in this order:

i)                The mock data of the entities and transactions are generated and stored as .csv and .json files.

ii)              The validator checks through the data using the pydantic contracts given and validates the data into valid and invalid. The invalid data are rerouted to the DLQ and stored in separate files to be referred later to check referential-integrity.

iii)            The valid records are stored in DuckDB and passed the Bronze Layer.

iv)            In the Silver Layer, the data is cleaned to remove trailing white spaces and consider the lowercase-uppercase discrepancies that might arise.

v)              Orphan transactions (transactions whose entities have been considered invalid in the bronze layer) are recognized and sent to a separate DLQ.

vi)            The valid records pass the silver layer and are rewritten in the Gold Star Schema format containing dim_entity, dim_date and fact_transactions.

vii)          The SQL queries to be executed are run against the final table and the results are displayed.

## **4.**     **TESTING:**

Pytest finds the test functions, runs them and checks whether the results match the expected results. The required tests were run and passed successfully.

i)                Test 1- Invalid email

ii)              Test 2- Negative transaction amount

iii)            Test 3- Missing entity

In addition to the tests mentioned, I also tested 7 more cases.

iv)            Test 4- Zero Amount rejected: Transactions with amount 0

v)              Test 5- Invalid currency

vi)            Test 6- Silver entities deduplicated: Duplicate entity records are removed during the Silver transform

vii)          Test 7- Orphan transactions sent to the DLQ

viii)        Test 8- Null entity

ix)            Test 9- Empty entity

x)              Test 10- Valid entity accepted

## **5.**     **ARCHITECTURE:**

A Medallion Architecture was built using Python, Pydantic and DuckDB with the following stages:

i)                Data generation: Generates the mock entity and transaction data with intentional errors and duplicates in .csv and .json files.

ii)              Validation (Bronze Layer): Pydantic holds its contracts to validate the records that have been created. Valid records gets stored in the tables in DuckDB whereas invalid records are sent to dead letter queues.

iii)            Cleaning and Transformation (Silver Layer): The trailing whitespaces, cases sensitivity and any other text related ambiguities are resolved and the duplicates are removed. Orphan transactions (transactions whose entities have been considered invalid in the bronze layer) are sent to a separate DLQ.

iv)            Star Schema (Gold Layer): For efficient analysis, the star schema is built with dim_date, dim_entity and fact_transactions.

v)              SQL queries: Analysis is done by executing the queries.

vi)            Integration: The single file with the entire pipeline is built and execution is done sequentially.

vii)          Testing: pytest is used to check if all the cases specified are handled successfully.

## **6.**     **DESIGN DECISIONS:**

Why the following was used:

i)                Pydantic:

Models in pydantic are built to define expected fields and data types for the necessary records. In our study, they are built in order to validate the UUIDs, emails, timestamps, transactions amounts and currency codes before loading into the bronze layer. The invalid errors are not discarded but stored by the DLQs instead of stopping the entire process.

ii)              DuckDB:

DuckDB is an SQL database that runs locally and doesn’t require a separate database server. It supports all SQL operations and tables that are required to be performed in this study.

iii)            Medallion Architecture (Bronze-Silver-Gold):

It is to separate the evaluation levels. Bronze is to pass the initial record validation. Silver is to standardize the data and remove duplicates. Gold is to organize the data for analysis. This levelling will make it easier to have track of what is being done and move the data level after level.

iv)            Star Schema:

This is done in order to have different data attributes organized separately in order to make analysis easier. The fact_transactions table would be the centre and the dim_entity and dim_date tables will be connected to the centre.

## **7.**   **RUN LOCALLY TO TEST:**

Run these commands after installing packages in requirements.txt:

python src/run_pipeline.py

python -m pytest -v
