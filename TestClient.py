import sys
import GSDEP

ip = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
port = sys.argv[2] if len(sys.argv) > 2 else 1337

c = GSDEP.Client(ip, port)

try:
	c.connect()

	c.send('STRTDAT')

	while True:
		print(c.recv())

except KeyboardInterrupt:
	c.close()
