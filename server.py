# import the necessary packages
from datetime import datetime
import imagezmq
import threading
import socket
import time

class coordinator:
    
    my_ip = 'localhost:9999'
    
    continue_server = {}
    continue_listening = False
    continue_send_request = False
    continue_send_reply = {}
    
    my_ports = [x for x in range(5555,5600)]
    
    senders = {}
    clients = []
    client_result = {}
    port_to_client = {}
    requests = []
    
    req_rep = False
    
    def __init__(self):        
        self.continue_listening = True
        client_manager = threading.Thread(target=self.manager)
        client_manager.start()
        
        self.continue_send_request = True
        request_thread = threading.Thread(target=self.send_request)
        request_thread.start()
        
    def server(self,ip,port):
        print('sub to : '+ip+':'+port)
        imageHub = imagezmq.ImageHub(open_port='tcp://'+str(ip)+':'+str(port),REQ_REP=False)
        
        frameDict = {}
        
        lastActive = {}
        lastActiveCheck = datetime.now()
        
        ESTIMATED_NUM_PIS = 4
        ACTIVE_CHECK_PERIOD = 10
        ACTIVE_CHECK_SECONDS = ESTIMATED_NUM_PIS * ACTIVE_CHECK_PERIOD
        
        #iterations=0
        
        while port in self.continue_server.keys() and self.continue_server[port]:
            (info, frame) = imageHub.recv_image()
            
            rpiName = info.split("||")[0]
            command = info.split("||")[1]
            frame_number = int(info.split("||")[2])
            #imageHub.send_reply(b'OK')
        	
            if rpiName not in lastActive.keys():
                print("[INFO] receiving data from {}...".format(rpiName))
        	
            lastActive[rpiName] = datetime.now()
        	
            frameDict[rpiName] = frame
         
            if (datetime.now() - lastActiveCheck).seconds > ACTIVE_CHECK_SECONDS:
        		
                for (rpiName, ts) in list(lastActive.items()):
        			
                    if (datetime.now() - ts).seconds > ACTIVE_CHECK_SECONDS:
                        print("[INFO] lost connection to {}".format(rpiName))
                        lastActive.pop(rpiName)
                        frameDict.pop(rpiName)
        		
                lastActiveCheck = datetime.now()
            
            if command=="request":
                #print("\n"+info)
                self.requests.append((info, frame))
                #if len(self.clients)>0:
                #    print("sending to.",self.clients[iterations%len(self.clients)])
                #    if self.clients[iterations%len(self.clients)]==rpiName:
                #        iterations+=1
                #    self.senders[self.clients[iterations%len(self.clients)]].send_image(info, frame)
                #    iterations+=1
            elif command=="processed":
                self.client_result[rpiName].append((info, frame))
        
        #imageHub.close_socket()
        del imageHub
        
    def send_reply(self,rpiName):
        while rpiName in self.continue_send_reply.keys() and self.continue_send_reply[rpiName]:
            if len(self.client_result[rpiName])>0:
                #print("sending to.",rpiName)
                info, frame = self.client_result[rpiName][0]
                self.client_result[rpiName].pop(0)
                self.senders[rpiName].send_image(info, frame)
				time.sleep(0.05)
                
    def send_request(self):
        iterations=0
        while self.continue_send_request:
            if len(self.requests)>0:
                info,frame = self.requests[0]
                self.requests.pop(0)
                rpiName = info.split("||")[0]
                clients = []
                for client in self.clients:
                    if client!=rpiName:
                        clients.append(client)
                if iterations%len(clients)==0:
                    time.sleep(0.08)
                if len(clients)>0:
                    #print("sending to.",self.clients[iterations%len(self.clients)])
                    #if self.clients[iterations%len(self.clients)]==rpiName:
                    #    iterations+=1
                    self.senders[clients[iterations%len(clients)]].send_image(info, frame)
                    iterations+=1
        
    def manager(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        server_address = ('', int(self.my_ip.split(":")[1]))
        print('\nlistening on %s port %s' % server_address)
        sock.bind(server_address)
        sock.settimeout(2)
        while self.continue_listening:
            try:
                message, client_address = sock.recvfrom(4096)
                message = message.decode('utf-8')
                if "join" in message:
                    address = message.split("||")[1]
                    #print("tcp://"+address.split(":")[0]+":"+address.split(":")[1])
                    self.clients.append(address)
                    available_port = self.my_ports[0]
                    self.port_to_client[address] = available_port
                    self.my_ports.pop(0)
                    print("pub to : "+"tcp://*"+":"+str(available_port))
                    sender = imagezmq.ImageSender(connect_to="tcp://*"+":"+str(available_port),REQ_REP=False)
                    self.senders[address] = sender
                    self.continue_server[address.split(":")[1]] = True
                    processing = threading.Thread(target=self.server,args=[address.split(":")[0],address.split(":")[1]])
                    processing.start()
                    sock.sendto(("ok||"+str(available_port)).encode('utf-8'),client_address)
                    
                elif "request" in message:
                    address = message.split("||")[1]
                    self.clients.remove(address)
                    self.client_result[address] = []
                    if address not in self.continue_send_reply.keys() or not self.continue_send_reply[address]:
                        self.continue_send_reply[address]= True
                        processing = threading.Thread(target=self.send_reply,args=[address])
                        processing.start()
                    sock.sendto("ok".encode('utf-8'),client_address)
                    
                elif "stop" in message:
                    address = message.split("||")[1]
                    self.clients.append(address)
                    #self.continue_send_reply.pop(address,None)
                    sock.sendto("ok".encode('utf-8'),client_address)
                    
                elif "end" in message:
                    address = message.split("||")[1]
                    port = self.port_to_client[address]
                    del self.port_to_client[address]
                    self.continue_server.pop(port,None)
                    self.my_ports.append(port)
                    if address in self.continue_send_reply.keys():
                        self.continue_send_reply.pop(address,None)
                    if address in self.clients:
                        self.clients.remove(address)
                    if address in self.senders.keys():
                        #self.senders[address].close_socket()
                        del self.senders[address]
                    sock.sendto("ok".encode('utf-8'),client_address)
            except socket.timeout:
                continue
        
        sock.close()
            
    def exit_threads(self):
        self.continue_server = {}
        self.continue_listening = False
        self.continue_send_request = False
            
if __name__=='__main__':
    c = coordinator()
    while True:
        a = input("\nEnter quit to exit\n")
        if a=="quit":
            c.exit_threads()
            print("done.")
            break