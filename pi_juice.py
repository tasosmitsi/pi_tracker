from pijuice import PiJuice

def init_pijuice():
    pijuice = PiJuice(1, 0x14) # Instantiate PiJuice interface object
    return pijuice