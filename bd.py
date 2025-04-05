import MySQLdb
from flask import Flask

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'sakila-db.cduews2gmidn.us-east-1.rds.amazonaws.com'
app.config['MYSQL_USER'] = 'admin'
app.config['MYSQL_PASSWORD'] = 'Admin123.'
app.config['MYSQL_DB'] = 'sakila'

def get_db_connection():
    return MySQLdb.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        passwd=app.config['MYSQL_PASSWORD'],
        db=app.config['MYSQL_DB']
    )