import telnetlib
import threading
from dwio import DWIO
import time
from dwlib import canonicalize

class DWTelnet(DWIO):
	def __init__(self, host='localhost', port=23):
		DWIO.__init__(self, threaded=True)
		self.host = host
		self.port = int(port)
		self.conn = None
		self.binding = None

	def isConnected(self):
		return self.conn != None

	def connect(self):
		self.conn = telnetlib.Telnet(self.host, self.port)
                self.conn.set_option_negotiation_callback(self._negotiate_echo_on)

	def _read(self, count=256):
		data = ''
		if not self.isConnected():
			return data
		try:
			#data = self.conn.read_very_eager()
			data = self.conn.read_some()
			if data == '':
				raise Exception("EOF")
		except Exception as ex:
			print str(ex)
			print "ERROR: Connection Closed"
			self._close()
		if self.debug and data != '':
			print "tel read:" , canonicalize(data)
		return data

	def _write(self, data):
		if not self.isConnected():
			return 0
		if self.debug and data != '':
			print "tel write:" , canonicalize(data)
		try:
			self.conn.write(data)
		except Exception as ex:
			print str(ex)
			print "ERROR: Connection Closed"
			self._close()
		return len(data)
	
	def _close(self):
		print "Closing Connection..."
		try:
			self.conn.close()
		except:
			pass
		self.conn = None
		self.abort = True

        def _negotiate_echo_on(self, sock, cmd, opt):
            # This is supposed to turn server side echoing on and turn other options off.
            sock = self.conn.get_socket()
            if opt == telnetlib.ECHO and cmd in (telnetlib.WILL, telnetlib.WONT):
               sock.sendall(telnetlib.IAC + telnetlib.DO + opt)
            elif opt != telnetlib.NOOPT:
                if cmd in (telnetlib.DO, telnetlib.DONT):
                   sock.sendall(telnetlib.IAC + telnetlib.WONT + opt)
                elif cmd in (telnetlib.WILL, telnetlib.WONT):
                   sock.sendall(telnetlib.IAC + telnetlib.DONT + opt)

if __name__ == '__main__':
	import sys


	sock = DWTelnet()
	
	def cleanup():
		#print "main: Closing sockial port."
		sock.close()
	import atexit
	atexit.register(cleanup)

	try:
		sock.connect()
		while True:
			print ">",
			wdata = raw_input()
			sock.write(wdata)
			#sock.write("\n> ")
			#print "main: Wrote %d bytes" % len(wdata)
			rdata = sock.readline()
			#print "main: Read %d bytes" % len(rdata)
			print rdata,
	finally:
		cleanup()
