import sys
from GSDEP import Server, GSDEPHandler, CHANNELS, CMDS
from time import sleep
import random
import logging
import threading

FORMAT = '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
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

	def connect(self, client):
		pass

	def disconnect(self, client):
		pass

	def recv(self, msg, client):
		payload = msg['msg']

		if payload in CMDS.values():
			if payload == CMDS['start_data']:
				if client not in self.requesting:
					self.requesting.append(client)
					logging.debug('Added %s to requesting', client.addr)
			if payload == CMDS['stop_data']:
				if client in self.requesting:
					logging.debug('Removed %s from requesting', client.addr)
					self.requesting.remove(client)
		else:
			print(payload)

	def send_sensor_data(self):
		logging.info('Started sensor data thread')
		while self.server.running:

			data = [[random.uniform(-i, i) for j in range(100)] for i in range(6)]

			self.server.multicast(self.requesting, data)
			sleep(0.1)


try:
	sensor = SensorHandler()
except KeyboardInterrupt:
	sensor.server.shutdown()

