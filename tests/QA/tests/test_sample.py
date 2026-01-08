import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from my_module import add_numbers, multiply_numbers


def test_add_numbers():
    """Тест проверяет сложение чисел"""
    assert add_numbers(2, 3) == 5   # 2+3 = 5 ✓
    assert add_numbers(-1, 1) == 0  # -1+1 = 0 ✓
    assert add_numbers(0, 0) == 0   # 0+0 = 0 ✓


def test_multiply_numbers():
    """Тест проверяет умножение чисел"""
    assert multiply_numbers(3, 4) == 12  # 3*4 = 12 ✓
    assert multiply_numbers(0, 5) == 0   # 0*5 = 0 ✓
    assert multiply_numbers(-2, 3) == -6 # -2*3 = -6 ✓
