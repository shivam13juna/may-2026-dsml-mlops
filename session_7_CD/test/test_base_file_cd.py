from session_6_CI.base_file import add, subtract, multiply, divide


def test_add():
	assert add(2, 3) == 5, "Expected add(2, 3) to be 5"
	assert add(-1, 1) == 0, "Expected add(-1, 1) to be 0"
	assert add(0, 0) == 0, "Expected add(0, 0) to be 0"


def test_subtract():
	assert subtract(5, 2) == 3, "Expected subtract(5, 2) to be 3"
	assert subtract(-1, 1) == -2, "Expected subtract(-1, 1) to be -2"
	assert subtract(0, 0) == 0, "Expected subtract(0, 0) to be 0"

def test_multiply():
	assert multiply(2, 3) == 6, "Expected multiply(2, 3) to be 6"
	assert multiply(-1, 1) == -1, "Expected multiply(-1, 1) to be -1"
	assert multiply(0, 0) == 0, "Expected multiply(0, 0) to be 0"

def test_divide():
	assert divide(6, 2) == 3, "Expected divide(6, 2) to be 3"
	assert divide(-6, 2) == -3, "Expected divide(-6, 2) to be -3"
	assert divide(0, 1) == 0, "Expected divide(0, 1) to be 0"
	assert divide(5, 0) == "Cannot divide by zero", "Expected divide(5, 0) to be 'Cannot divide by zero'"