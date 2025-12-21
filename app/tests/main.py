def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract two numbers."""
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


def divide(a: float, b: float) -> float:
    """Divide two numbers."""
    if b == 0:
        msg = "Cannot divide by zero"
        raise ValueError(msg)
    return a / b


def is_even(n: int) -> bool:
    """Check if a number is even."""
    return n % 2 == 0
