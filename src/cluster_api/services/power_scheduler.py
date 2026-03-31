from gpiozero import LED as IO

def turn_on_node(gpio: int):
    """Turn on the node."""
    IO(gpio).on()

