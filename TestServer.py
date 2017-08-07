import GSDEP

s = GSDEP.Server('', 1337)

try:
	s.start()
except KeyboardInterrupt:
	s.shutdown()
