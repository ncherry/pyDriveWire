import threading
import traceback
import subprocess
from dwsocket import *
from dwtelnet import DWTelnet
import os
import sys

class ParseNode:
	def __init__(self, name, nodes=None):
		self.name = name
		self.nodes = {}
		if nodes:
			self.nodes = nodes
	def add(self, key, val):
		self.nodes[key]=val

	def lookup(self, key):
                if not key:
                        return None
                # exact match
		r = self.nodes.get(key, None)
                if r:
                        return r
                key = key.lower()
       		r = self.nodes.get(key, None)
                if r:
                    return r
                # search partial
                allNodes = self.nodes.keys()
                for i in range(len(key)+1):
                    s = key[:i]
                    nodes = [n for n in allNodes if n.startswith(s)]
                    #print i,"(%s"%s,nodes
                    if len(nodes) == 1:
                        key = nodes[0]
                        return self.nodes.get(key, None)
                return None       
                        
	def repr(self):
		return str(nodes)

	def help(self):
		p = []
		if self.name:
			p.append(self.name)
		p.append("commands:")
		p.extend(self.nodes.keys())
		return "%s" % (' '.join(p))

class ATParseNode(ParseNode):
	def __init__(self, name, nodes=None):
		ParseNode.__init__(self, name, nodes)

	def lookup(self, key):
		k = key[0]
		r =  ParseNode.lookup(self, k)
		if not r:
			k = key[0:1]
			r =  ParseNode.lookup(self, k.upper())
		return r

	def help(self):
		#if self.name:
		#	p.append(self.name)
		p=["commands:"]
		p.extend(["AT%s"%k for k in self.nodes])
		return "%s" % (' '.join(p))

class ParseAction:
	def __init__(self, fn):
		self.fn = fn
	
	def call(self, *args):
		return self.fn(*args)
			
	def repr(self):
		return fn
class DWParser:
	def setupParser(self):
		diskParser=ParseNode("disk")
		diskParser.add("insert", ParseAction(self.doInsert))
		diskParser.add("reset", ParseAction(self.doReset))
		diskParser.add("eject", ParseAction(self.doEject))
		diskParser.add("show", ParseAction(self.doShow))

		serverParser=ParseNode("server")
		serverParser.add("instance", ParseAction(self.doInstance))
		serverParser.add("dir", ParseAction(self.doDir))
		serverParser.add("list", ParseAction(self.doList))
		serverParser.add("dump", ParseAction(self.dumpstacks))
		serverParser.add("debug", ParseAction(self.doDebug))
		serverParser.add("timeout", ParseAction(self.doTimeout))
		connParser=ParseNode("conn")
		connParser.add("debug", ParseAction(self.doConnDebug))
		serverParser.add("conn", connParser)

		portParser=ParseNode("port")
		portParser.add("show", ParseAction(self.doPortShow))
		portParser.add("close", ParseAction(self.doPortClose))
		portParser.add("debug", ParseAction(self.doPortDebug))

		dwParser=ParseNode("dw")
		dwParser.add("disk", diskParser)
		dwParser.add("server", serverParser)
		dwParser.add("port", portParser)

		tcpParser=ParseNode("tcp")
		tcpParser.add("connect", ParseAction(self.doConnect))
		tcpParser.add("listen", ParseAction(self.doListen))
		tcpParser.add("join", ParseAction(self.doJoin))
		tcpParser.add("kill", ParseAction(self.doKill))

		atParser=ATParseNode("AT")
		atParser.add("", ParseAction(lambda x: {'msg': 'OK', 'self.cmdAutoClose': False}))
		atParser.add("Z", ParseAction(lambda x: {'msg': 'OK', 'self.cmdAutoClose': False}))
		atParser.add("D", ParseAction(self.doDial))
		atParser.add("DT", ParseAction(self.doDial1))
		atParser.add("I", ParseAction(lambda x: {'msg': 'pyDriveWire %s\r\nOK'%self.server.version, 'self.cmdAutoClose': False}))
		atParser.add("O", ParseAction(lambda x: {'msg': 'OK', 'self.cmdAutoClose': False, 'self.online': True}))
		atParser.add("H", ParseAction(lambda x: {'msg': 'OK', 'self.cmdAutoClose': False, 'self.online': False}))
		atParser.add("E", ParseAction(lambda x: {'msg': 'OK', 'self.cmdAutoClose': False, 'self.echo': True}))

		uiSFileParser=ParseNode("file")
		uiSFileParser.add("defaultdir", ParseAction(self.doUSFdefaultdir))
		uiSFileParser.add("dir", ParseAction(self.doUSFdir))
		uiSFileParser.add("info", ParseAction(self.doUSFinfo))
		uiSFileParser.add("roots", ParseAction(self.doUSFroots))
		uiSFileParser.add("xdir", ParseAction(self.doUSFxdir))

		uiServerParser=ParseNode("server")
                uiServerParser.add("file", uiSFileParser)

		uiParser=ParseNode("ui")
                uiParser.add("server", uiServerParser)

		self.parseTree=ParseNode("")
		self.parseTree.add("dw", dwParser)
		self.parseTree.add("tcp", tcpParser)
		self.parseTree.add("AT", atParser)
		self.parseTree.add("ui", uiParser)

	def __init__(self, server):
		self.server=server
		self.setupParser()

	def doInsert(self, data):
		opts = data.split(' ')
		if len(opts) != 2:
			raise Exception("dw disk insert <drive> <path>")
		(drive, path) = opts
		self.server.open(int(drive), path)
		return "open(%d, %s)" % (int(drive), path)

	def doReset(self, data):
		drive = int(data.split(' ')[0])
		path = self.server.files[drive].file.name
		self.server.close(drive)
		self.server.open(drive, path)
		return "reset(%d, %s)" % (int(drive), path)

	def doEject(self, data):
		drive = data.split(' ')[0]
		self.server.close(int(drive))
		return "close(%d)" % (int(drive))
	def doInstance(self, data):
		out = ['','']
		out.append( "Inst.  Type" )
		out.append( "-----  --------------------------------------" )
		#i=0
		#for f in self.server.files:
		out.append( "%d      %s" % (0, self.server.conn.__class__))
		#	i += 1
		
		out.append('')
		return '\n\r'.join(out)

	def doPortClose(self, data):
		channel = data.lstrip().rstrip()
		if not chr(int(channel)) in self.server.channels:
			return "Invalid port %s" % channel
		ch = self.server.channels[channel]
		ch._close()
		return "Port=n%s closing" % channel

	def doPortShow(self, data):
		out = ['','']
		out.append( "Port   Status" )
		out.append( "-----  --------------------------------------" )
		i=0
		for i,ch in self.server.channels.items():
			co=ch.conn	
			connstr = " Online" if ch.online else "Offline"
			if co:
				direction = " In" if ch.inbound else "Out"
				connstr = "%s %s %s:%s" % (connstr, direction, co.host, co.port)
			out.append( "N%d      %s" % (int(ord(i)), connstr))
		
		out.append('')
		return '\n\r'.join(out)

	def doPortDebug(self, data):
		dv = data.split(' ')
		cn = dv[0]
		channel = chr(int(cn))
		if not chr(int(channel)) in self.server.channels:
			return "Invalid port %s" % cn
		state = None
		if len(dv)>1:
			state = dv[1]	
		ch = self.server.channels[channel]
		if state.startswith(('1','on','t','T','y', 'Y')):
			ch.debug = True
		if state.startswith(('0','off','f','F','n', 'N')):
			ch.debug = False
		return "Port=N%s debug=%s" % (cn, ch.debug)

	def doShow(self, data):
		out = ['','']
		out.append( "Drive  File" )
		out.append( "-----  --------------------------------------" )
		i=0
		for f in self.server.files:
			name = f.name if f else f
			if f and f.remote:
				name += '(%s)' % f.file.name
			out.append( "%d      %s" % (i, name) )
			i += 1
		
		out.append('')
		return '\n\r'.join(out)

	def doConnDebug(self, data):
		if data.startswith(('1','on','t','T','y', 'Y')):
			self.server.conn.debug = True
		if data.startswith(('0','off','f','F','n', 'N')):
			self.server.conn.debug = False
		return "debug=%s" % (self.server.conn.debug)

	def doTimeout(self, data):
		opts = data.split(' ')
		if opts:
			timeout = float(opts[0])
			self.server.timeout = timeout
		return "debug=%s" % (self.server.timeout)
			
	def doDebug(self, data):
		if data.startswith(('1','on','t','T','y', 'Y')):
			self.server.debug = True
		if data.startswith(('0','off','f','F','n', 'N')):
			self.server.debug = False
		return "debug=%s" % (self.server.debug)
			
	#def doDir(self, data, nxti):
	def doDir(self, data):
		out = ['']
		cmd = ['ls']
		#if nxti != -1:
		#	path = data[nxti+1:].split(' ')[0]
		#	cmd.append(path)
		#if not data:
		#	raise Exception("dir: Bad data")
		if data:
			cmd.append(data)
		print cmd
		data2 = subprocess.Popen(
			" ".join(cmd),
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			shell=True)	
		out.extend(data2.stdout.read().split('\n'))
		out.append('')
		return '\n\r'.join(out)

	def doList(self, path):
		out = []
		cmd = ['cat']
		#path = data.split(' ')[0]
		if not path:
			raise Exception("list: Bad Path")
		cmd.append(path)
		data2 = subprocess.Popen(
			" ".join(cmd),
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			shell=True)	
		out.extend(data2.stdout.read().strip().split('\n'))
		#out.append('')
		return '\n\r'.join(out)

	def doDial1(self, data):
		return self.doConnect(data[1:], telnet=True)
		#return self.doDial(data[1:])

	def doDial(self, data):
                if data.startswith('T'):
                    data = data[1:]
		#i = data.index(':')
		#if i >= 0:
		#	data[i] = ' '
		return self.doConnect(data, telnet=True)

	def doConnect(self, data, telnet=False):
		r = data.split(':')
		if len(r)==1:
			r = data.split(' ')
		if len(r)==1:
			r.append('23')
		(host,port) = r
		print "host (%s)" % host
		print "port (%s)" % port
		if not host and not port:
                    raise Exception("telnet: Bad Host/Port: %s" % data)
		try:
			if telnet:
				sock = DWTelnet(host=host, port=port)
                                res = {'msg': '\r\nCONNECTED', 'obj': sock, 'self.cmdAutoClose': False, 'self.online': True}
			else:
				sock = DWSocket(host=host, port=port)
                                res = sock
			sock.connect()
		except Exception as ex:
			res = "FAIL %s" % str(ex)
		return res

	def doListen(self, data):
		r = data.split(' ')
		port = r[0]
		return DWSocketListener(port=port)

	def doKill(self, data):
		#r = data.split(':')
		conn = self.server.connections.get(data,None)
		if not conn:
			raise Exception("Invalid connection: %s" % data)
		res =  "OK killing connection %s\r\n" % data
		print res
		conn.binding = None
		conn.close()
		del self.server.connections[r]
		return res

	def doJoin(self, data):
		#r = data.split(':')
		
		conn = self.server.connections.get(data,None)
		print "Binding %s to %s" % (conn, data)
		if not conn:
			raise Exception("Invalid connection: %s" % data)
		conn.binding = data
		return conn
		

	def dumpstacks(self, data):
            import threading, sys, traceback
	    id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
	    code = []
	    for threadId, stack in sys._current_frames().items():
		code.append("\n# Thread: %s(%d)" % (id2name.get(threadId,""), threadId))
		for filename, lineno, name, line in traceback.extract_stack(stack):
		    code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
		    if line:
			code.append("  %s" % (line.strip()))
	    return "\r\n".join(code)

        def doUSFdir(self, data):
            r = []
            if os.path.isdir(data):
                dd = [os.path.join(data, d) for d in listdir(data)]
            else:
                dd = [data]
            for path in dd:
                rr = [os.path.sep]
                rr += [path]
                rr += [data]
                s = os.stat(path)
                rr += ["%d" % s.st_size] 
                rr += ["%d" % s.st_mtime] 
                rr += ["true" if os.path.isdir(path) else "false"]  # readable
                rr += ["false"]  # writable
                re = '|'.join(rr)
                r.append(re)
            return '\n'.join(r)


        def doUSFdefaultdir(self, data):
            raise Exception("Command not implemented")

        def doUSFinfo(self, data):
            raise Exception("Command not implemented")

        def doUSFroots(self, data):
            r = []
            if os.name == 'posix':
                r += ["/"]
            else:
                from win32com.client import Dispatch
                fso = Dispatch('scripting.filesystemobject')
                for i in fso.Drives:
                        r += [i]
            return "\n".join(r)

        def doUSFxdir(self, data):
            import stuct
            r = []
            if os.path.isdir(data):
                dd = [os.path.join(data, d) for d in listdir(data)]
            else:
                dd = [data]
            for path in dd:
                s = os.stat(data)
                mt = time.localtime(s.st_mtime)
                e = struct.pack(
                    ">IBBBBBBBB",
                    s.st_size&0xffffffff,
                    mt[0], # tm_year
                    mt[1], # tm_mon
                    mt[2], # tm_mday
                    mt[3], # tm_hour
                    mt[4], # tm_min
                    os.path.isdir(path),
                    os.access(path, W_OK),
                    len(data)
                )
                e += data
                r += [e] 
            return '\n'.join(r)
		
	def parse(self, data, interact=False):
		data = data.lstrip().strip()
		u = data.upper()
		if u.startswith("AT"):
			tokens=["AT"]
			t2 = u[2:]
			if t2:
				tokens.append(t2)
			else:
				return {'res': "OK", 'self.online':True}
		else:
			tokens = data.split(' ')
		p = self.parseTree
		i = 0
		for t in tokens:
			#print t
			v=p.lookup(t)
			#print v
			if v:
				i += len(t) + 1
			if isinstance(v, ParseNode):
				p = v
			elif isinstance(v, ParseAction):
				if tokens[0] == "AT":
					callData = data[3:].lstrip()
				else:
					callData = data[i:]
				print callData
				res = ''
				try:
					res=v.call(callData)	
				except Exception as ex:
					if interact:
						raise
					res="FAIL %s" % str(ex)
				return res
			else:
				break

		msg = []
		if t:
			msg.append("%s: Invalid command: %s" % (p.name, t))
		msg.append(p.help())
		#msg.append('')
		return '\n\r'.join(msg)
		# raise Exception("%s: Invalid" % data)
		
class DWRepl:
	def __init__(self, server):
		self.server = server
		self.parser = DWParser(self.server)
		self.rt = threading.Thread(target=self.doRepl, args=())
		self.rt.daemon = True
		self.rt.start()

	def doRepl(self):
		while True:
			try: 
				print "pyDriveWire> ",
				wdata = raw_input()
			except EOFError:
				print
				print "Bye!"
				break
			
			# basic stuff
			if wdata.find(chr(4)) == 0 or wdata.lower() in ["exit", "quit"] :
				# XXX Do some cleanup... how?
				print "Bye!"
				break
			
			try:
				print self.parser.parse(wdata, True)
			except Exception as ex:
				print "ERROR:: %s" % str(ex)
				traceback.print_exc()

		self.server.conn.cleanup()
		i=0
		for f in self.server.files:
			if f:
				self.server.close(int(i))
			i += 1
		os._exit(0)
if __name__ == '__main__':
	r = DWRepl(None)
	r.rt.join()

#finally:
#	cleanup()
