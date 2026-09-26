from fasturl.hello import say_hello


def test_say_hello() -> None:
    assert say_hello(name="World") == "Hello, World!"
    assert say_hello(name="Alice") == "Hello, Alice!"
    assert say_hello(name="Bob") != "Hello, Alice!"
