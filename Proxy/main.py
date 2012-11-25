#Authors: Bobby Davis, Matt Cotter
#Date: 11/16/2011
#
#NOTES: Please run this in it's own folder as it will crawl all subdirectories
#       to delete empty folders on exiting.

import time
import datetime
import BaseHTTPServer
import urllib2
import os
import sys
import mimetools


HOST_NAME = '' 
PORT_NUMBER = 8000 


class CachedFile():	 #this is a file stored on the hard drive
	def __init__(self, name, status=None, headers = None, body=None):
		self.isCachy = True
		self.name = name
		if name[len(name)-1] == "/":
			self.name = self.name + "index.html"
		if len(name)>200: #if name is too long
			self.name = "temp/temp.html"
			self.cachy = False
		if status != None: #if we want to create a new file
			dir = os.path.dirname(self.name)
			if not os.path.exists(dir):
				os.makedirs(dir);
			with open(self.name,'w') as f:
				f.write(body);
			found = 0
			t = None
			h = headers.getheader("expires")
			if h == None:
				h = headers.getheader("date")
				self.expiresTime  = time.mktime(time.strptime(h,"%a, %d %b %Y %H:%M:%S %Z"))+300
			else:
				try:
					self.expiresTime  = time.mktime(time.strptime(h,"%a, %d %b %Y %H:%M:%S %Z"))
				except:
					self.expiresTime = 0 #this will always be expired.
			headerList = []
			for h in headers:
				headerList.append((h,headers.getheader(h)))
			headerList.insert(0,('StatusCode',status))
			with open(self.name+'.headers', 'w') as f:
				f.write(str(headerList))
		else: #file already exists on disk
			headers = self.getHeaders()
			self.expiresTime = 0
			for h in headers:
				if h[0] == 'expires':
					self.expiresTime  = time.mktime(time.strptime(h[1],"%a, %d %b %Y %H:%M:%S %Z"))
					break
		self.size = os.path.getsize(self.name)+os.path.getsize(self.name+'.headers')
		self.setIsCachy()
	
	def getStatus(self): #returns HTTP status code
		res	 = None
		with open(self.name+".headers",'r') as f:
			res = eval(f.read())
		return res[0][1]
	
	def updateHeaders(self, status, headers): #updates headers to new date and expiration time.
		found = 0;
		t = None
		h = headers.getheader("expires")
		if h == None:
			h = headers.getheader("date")
			self.expiresTime  = time.mktime(time.strptime(h,"%a, %d %b %Y %H:%M:%S %Z"))+300
		else:
			self.expiresTime  = time.mktime(time.strptime(h,"%a, %d %b %Y %H:%M:%S %Z"))
		headerList = []
		for h in headers:
			headerList.add((h,headers.getheader(h)))
		headerList.insert(0,('StatusCode',status))
		with open(self.name+'.headers', 'w') as f:
			f.write(str(headerList))
		self.size = os.path.getsize(self.name)+os.path.getsize(self.name+'.headers')
		self.setIsCachy()
	
	def getHeaders(self): #returns list of header tuples
		res	 = None
		with open(self.name+".headers",'r') as f:
			res = eval(f.read())
		return res[1:]
		
	def getBody(self): #returns body of HTTP message
		res	 = None
		with open(self.name,'r') as f:
			res = f.read()
		return res
		
	def getSize(self):
		return self.size
		
	def isExpired(self):
		return self.expiresTime<time.mktime(time.gmtime())
		
	def getDate(self):
		res = self.getHeaders();
		for h in res:
			if h[0] == 'date':
				return h[1]
				
	def updateDate(self):
		res	 = self.getHeaders()
		for h in res:
			if h[0] == 'date':
				rem = h
				tup = (h[0], time.strftime("%a, %d %b %Y %H:%M:%S",time.gmtime())+" GMT")
		res.remove(rem)
		res.append(tup)
		res.insert(0,("StatusCode", self.getStatus()))
		with open(self.name+".headers",'w') as f:
			f.write(str(res))
			
	def setIsCachy(self):
		#if cahchable status code
		self.isCachy = self.isCachy and self.getStatus() in [200, 203, 206, 300, 301, 410]
		
		headers = self.getHeaders()
		for h in headers:
			if h[0] == 'cache-control': #check if we can cache this
				value = h[1].split(',')
				smax = 0
				for v in value:
					self.isCachy = self.isCachy and v.split('=')[0].strip() not in ['private','no-cache']
					if v.split('=')[0].strip() =='s-maxage':
						smax=1
						self.expiresTime = time.mktime(time.gmtime()) + int(v.split('=')[1].strip())
					elif v.split('=')[0].strip() =='max-age' and not smax:
						self.expiresTime = time.mktime(time.gmtime()) + int(v.split('=')[1].strip())
				break
	
	def compareDate(self,d): #for conditional GETs
		# returns THIS date subtract GIVEN date
		headers = self.getHeaders()
		for h in headers:
			if h[0] == "date":
				break
		thisT = time.mktime(time.strptime(h[1],"%a, %d %b %Y %H:%M:%S %Z"))
		t = time.mktime(time.strptime(d,"%a, %d %b %Y %H:%M:%S %Z"))
		return thisT - t
		
		
	def delete(self): #deletes the file from the disk, and makes sure file is removed from the files cache
		os.remove(self.name)
		os.remove(self.name+'.headers')
		filesCache.removeNoDelete(self)

class Cache():
	def __init__(self):
		self.files = []
		self.size = 0
		self.maxSize = 100*1024 #in bytes
		self.readFile()
		
	def __repr__(self):
		a = ""
		for f in self.files:
			a += "\t"+f.name
		return a
	
	def add(self, file):
		if file.size<self.maxSize and file.isCachy and not (file.name == 'temp/temp.html'): #don't cache if temp, because this either too long of a nme, or a conditional GET
			if self.contains(file.name):
				self.removeName(file.name)
			while (self.size + file.size) > self.maxSize:
				f = self.files.pop(0)
				self.size-=f.size
				f.delete()
			self.files.append(file)
			self.size += file.size
			
	def remove(self, f):
		if f in self.files:
			self.files.remove(f)
			f.delete()
			
	def removeNoDelete(self, f): #called from CachedFile.delete()
		if f in self.files:
			self.files.remove(f)
			
	def removeName(self, name):
		for f in self.files:
			if f.name == name:
				self.files.remove(f)
				f.delete()
	
	def contains(self, name):
		if name[len(name)-1] == "/":
			name = name + "index.html"
		for f in self.files:
			if f.name == name:
				return True
		return False
		
	def get(self, name):
		for f in self.files:
			if f.name == name:
				break
		self.files.remove(f)
		f.updateDate()
		self.files.append(f) #brings file to end of list
		return f
		
		
	def getNode(self, name): #takes in a file path and returns (path, [sub paths], [filenames])
		for r in os.walk(name):
			return r
	
	def purgeEmpty(self, node): #removes all empty folders in current directory (called recursively)
		path = node[0]+'/'
		if len(node[1])!=0: #if has subfolders
			for child in node[1]:
				self.purgeEmpty(self.getNode(path+child))
			node = self.getNode(node[0])
		if len(node[1])==0: #currently has no sub folders
			for x in node[2]:
				if x == ".DS_Store": #remove all .DS_Store files
					node[2].remove(x)
					os.remove(path+".DS_Store")
			if len(node[2])==0: #this folder has no files
				os.rmdir(node[0]) #so delete it!
	
	def writeFile(self): #stores the cache in a file to be read on next start up.
		with open('filesCache','w') as f:
			fnames = []
			for file in self.files:
				if not file.isExpired():
					fnames.append(file.name)
				else:
					file.delete()
			f.write(str(fnames))
		print "Removing empty folders..."
		self.purgeEmpty(self.getNode(os.getcwd())) #Because of this, you should probably have main.py in it's own folder when you start
	
	def readFile(self): #reads previously stored cache
		try:
			with open('filesCache','r') as f:
				fnames = eval(f.read())
			for name in fnames:
				f = CachedFile(name)
				if f.isExpired():
					f.delete()
				else:
					self.add(f)
		except:
			pass
		
		
filesCache = Cache() #Global so that it doesn't get reset on every handle_request

class MessageHeaders: #class so we can pass a list of header tuples to CachedFile initializer
	def __init__(self, heads):
		self.headers = heads
		
	def __iter__(self):
		self.counter = 0
		return self
		
	def next(self):
		if self.counter>=len(self.headers):
			raise StopIteration
		else:
			self.counter += 1
			return self.headers[self.counter-1][0]
		
	def getheader(self, name):
		for h in self.headers:
			if h[0]==name:
				return h[1]
		return None
	
	

class HTTPProxyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def __init__(self, request, client_address, thisHTTPServer):
		BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, request, client_address, thisHTTPServer)
		#set timeouts
		thisHTTPServer.timeout= 1
		self.timeout = 1
		#allow persistent connections
		self.protocol_version = "HTTP/1.1"
	
	def isHopHeader(self, name): #all headers that shouldn't be passed on
		return name in ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade']
		
	def addHopHeaders(self, req): #for message to origin server
		req.add_header("connection", "close")
	
	def isConditionalGet(self, f):
		for h in self.headers:
			if h == "if-modified-since":
				return f.compareDate(self.headers.getheader(h)) > 0
			elif h == "if-unmodified-since":
				return f.compareDate(self.headers.getheader(h)) < 0
		return False
		
	def do_HEAD(self):
		self.do_both(False)
	
	def do_GET(self):
		self.do_both(True)
	
	def do_both(self, isGET):
		host = self.path.partition("://")[2].partition("/")[0]
		port = self.path.partition("://")[2].rpartition(":")[2]
		file = ""
		if port != "":
			try:
				int(port)
				port = ":" + port
				file = "/"+self.path.partition("://")[2].partition("/")[2].rpartition(":")[0]
			except:
				file = "/"+self.path.partition("://")[2].partition("/")[2]
				port = ""

		print "Host: " + host + "\nPort: " + port + "\nFile: " + file
		
		print filesCache
		
		finalFile = None
		
		#check for local copies
		if filesCache.contains(host+file):
			print "File found in cache!"
			f = filesCache.get(host+file)
			if not f.isExpired():
				print "Not Expired!"
				if self.isConditionalGet(f):
					print "Is Conditional"
					finalFile = CachedFile("temp/temp.html", 304, MessageHeaders(f.getHeaders()), '')
					finalFile.isCachy = False
				else:
					print "Not conditional"
					finalFile = f
			else:
				print "File is expired!"
				#send conditional get to server
				req = urllib2.Request("http://"+host+file+port)
				for h in self.headers:
					if not self.isHopHeader(h):
						req.add_header(h,self.headers.getheader(h))
				self.addHopHeaders(req)
				req.add_header("If-Modified-Since", f.getDate())
				url_handle = urllib2.build_opener(urllib2.BaseHandler()).open(req)
				if hasattr(url_handle, 'code') and url_handle.code == 304:
					print "File has not been modified."
					#just return cached copy, updating the headers
					f.updateHeaders(200, url_handle.info())
					if self.isConditionalGet(f):
						finalFile = CachedFile("temp/temp.html", 304, MessageHeaders(f.getHeaders()), '')
						finalFile.isCachy = False
					else:
						finalFile = f
				else:
					print "File has been modified."
					filesCache.remove(f)
					finalFile = CachedFile(host+file, url_handle.code, url_handle.info(), url_handle.read())
					filesCache.add(finalFile)
		else:
			print "File not found in cache"
			req = urllib2.Request("http://"+host+file+port)
			for h in self.headers:
				if not self.isHopHeader(h):
					req.add_header(h,self.headers.getheader(h))
			self.addHopHeaders(req)
			try:
				url_handle = urllib2.build_opener(urllib2.BaseHandler()).open(req)
				finalFile = CachedFile(host+file, url_handle.code, url_handle.info(), url_handle.read())
				filesCache.add(finalFile)
			except urllib2.HTTPError:
				if '304' in str(sys.exc_info()[1]): #file not modified
					temp = sys.exc_info()[1]
					finalFile = CachedFile("temp/temp.html", 304, temp.info(), '')
					finalFile.isCachy = False
				elif '404' in str(sys.exc_info()[1]):
					temp = sys.exc_info()[1]
					finalFile = CachedFile("temp/temp.html", 404, temp.info(), 'File Not Found')
					finalFile.isCachy = False
				elif '403' in str(sys.exc_info()[1]):
					temp = sys.exc_info()[1]
					finalFile = CachedFile("temp/temp.html", 403, temp.info(), 'Forbidden')
					finalFile.isCachy = False
				else:
					print str(sys.exc_info()[1])
					return
			
			
		#send the final file
		self.send_response(finalFile.getStatus())
		for header in finalFile.getHeaders():
			if not self.isHopHeader(header[0]):
				self.send_header(header[0], header[1])
		temp = self.headers.getheader('connection')
		if not (temp == None):
			self.send_header('connection', temp)
		self.end_headers()
		if(isGET):
			self.wfile.write(finalFile.getBody())
		if not filesCache.contains(finalFile.name):
			finalFile.delete()

if __name__ == '__main__':
	server_class = BaseHTTPServer.HTTPServer
	httpd = server_class((HOST_NAME, PORT_NUMBER), HTTPProxyHandler)
	print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER)
	print str(filesCache)
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		pass
	httpd.server_close()
	filesCache.writeFile()
	print time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER)
	
