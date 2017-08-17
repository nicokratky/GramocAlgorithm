import sys
from GSDEP import Server, GSDEPHandler, CHANNELS, CMDS
from time import sleep
import random
import logging
import threading

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)

IP = sys.argv[1] if len(sys.argv) > 1 else ''
PORT = int(sys.argv[2] if len(sys.argv) > 2 else 1337)

class SensorHandler(GSDEPHandler):
	def __init__(self):
		super().__init__()

		self.server = Server(self, IP, PORT)

	def connect(self, sock):

	def disconnect(self, sock):
		pass

	def recv(self, msg, sock):
		pass

try:
	sensor = SensorHandler()
except KeyboardInterrupt:
	sensor.server.shutdown()

