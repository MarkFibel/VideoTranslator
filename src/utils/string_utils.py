import re

def to_snake_case(name: str) -> str:
    """
    Преобразует строку из CamelCase в snake_case.
    Например, 'SomeTestService' -> 'some_test_service'.
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
