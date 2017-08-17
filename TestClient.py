import sys
from GSDEP import Client, CHANNELS, CMDS
import logging
from time import sleep, time
import threading

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)

IP = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = sys.argv[2] if len(sys.argv) > 2 else 1337

try:
	c = Client(IP, PORT)
	c.connect()

	c.send(CMDS['start_data'])

	start = time()
	while start + 5 > time():
		print(c.recv())
except KeyboardInterrupt:
	pass
finally:
	c.close()
