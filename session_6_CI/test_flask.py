import pytest
import numpy as np

from hello import pancakes


# purpose of fixture is to create resources that can be shared across tests

# pytest fixture for connecting to a database
#@pytest.fixture
#def db_connection():
#	# Simulate a database connection
#	connection = "Database connection established"
#	yield connection
#	# Teardown code
#	connection = None
#	print("Database connection closed")

## use the fixture in a test
#def test_db_connection(db_connection):
#	assert db_connection == "Database connection established"


#@pytest.fixture
#def create_something():
#	return "something"


#def testing_wednesday(create_something):
#	assert create_something == "something"

@pytest.fixture
def client():
	return pancakes.test_client() # test_client() is a function provided by Flask to simulate requests to the application without running a server

def test_my_first_flask_function(client):
	response = client.get('/monday') #.get is used to simulate a GET request to the specified endpoint

	assert response.data == b'No!!! It is Monday!'
	assert response.status_code == 200