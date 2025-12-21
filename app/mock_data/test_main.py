import pytest
from main import add, subtract, multiply, divide, is_even


class TestMathFunctions:
    """Tests for math functions"""

    def test_add(self):
        """Test addition function"""
        assert add(2, 3) == 5
        assert add(-1, 1) == 0
        assert add(0, 0) == 0

    def test_subtract(self):
        """Test subtraction function"""
        assert subtract(5, 3) == 2
        assert subtract(10, 15) == -5
        assert subtract(0, 0) == 0

    def test_multiply(self):
        """Test multiplication function"""
        assert multiply(3, 4) == 12
        assert multiply(-2, 5) == -10
        assert multiply(0, 100) == 0

    def test_divide(self):
        """Test division function"""
        assert divide(10, 2) == 5
        assert divide(9, 3) == 3
        assert divide(7, 2) == 3.5

        # Test division by zero
        with pytest.raises(ValueError):
            divide(10, 0)

    def test_is_even(self):
        """Test even number check function"""
        assert is_even(2) is True
        assert is_even(0) is True
        assert is_even(-4) is True
        assert is_even(3) is False
        assert is_even(1) is False
        assert is_even(-5) is False
