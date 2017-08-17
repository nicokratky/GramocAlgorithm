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

		self.requesting = []

		t = threading.Thread(target=self.send_sensor_data, daemon=True)
		t.start()

	def connect(self, sock):
		pass

	def disconnect(self, sock):
		pass

	def recv(self, msg, sock):
		payload = msg['msg']

		if payload in CMDS.values():
			if payload == CMDS['start_data']:
				if sock not in self.requesting:
					self.requesting.append(sock)
					logging.debug('Added %s to requesting', sock.getpeername())
			if payload == CMDS['stop_data']:
				if sock in self.requesting:
					self.requesting.remove(sock)
					logging.debug('Removed %s from requesting', sock.getpeername())
		else:
			print(payload)

	def send_sensor_data(self):
		logging.info('Started sensor data thread')
		while self.server.running:
			data = [random.uniform(-1.8, 1.8), random.uniform(-1.8, 1.8), random.uniform(-1.8, 1.8)]
			self.server.multicast(self.requesting, data)


try:
	sensor = SensorHandler()
except KeyboardInterrupt:
	sensor.server.shutdown()

