import sys
import GSDEP
from sense_hat import SenseHat

ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.101.52'
port = sys.argv[2] if len(sys.argv) == 3 else 1337

s = GSDEP.Server(ip, port)

def sensor():
	sense = SenseHat()
	raw = sense.get_accelerometer_raw()
	return [raw['x'], raw['y'], raw['z']]

s.attach_readout_function(sensor)

try:
	s.start()
except KeyboardInterrupt:
	s.shutdown()
