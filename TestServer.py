import sys
import GSDEP
from time import sleep
import random

ip = sys.argv[1] if len(sys.argv) > 1 else ''
port = int(sys.argv[2] if len(sys.argv) > 2 else 1337)

s = GSDEP.Server(ip, port)

def sensor():
	sleep(0.01)
	return [random.uniform(-1.8, 1.8), random.uniform(-1.8, 1.8), random.uniform(-1.8, 1.8)]

s.attach_readout_function(sensor)

try:
	s.start()
except KeyboardInterrupt:
	s.shutdown()
