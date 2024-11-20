import socket
import threading
import os
from tool import *
from file import File
import random
import time
import pickle
from threading import Thread
import sys

PEER_IP = get_host_default_interface_ip()
LISTEN_DURATION = 5
PORT_FOR_PEER= random.randint(12600, 22000)

class peer:
    def __init__(self):
        self.peerIP = PEER_IP # peer's IP
        self.peerID = PORT_FOR_PEER # peer' ID
        self.portForPeer = PORT_FOR_PEER #* port for peer listening conection with other peers
        self.portForTracker = PORT_FOR_PEER + 1 # *?  port for peer listening connection with tracker. Should this be used ?
        self.lock = threading.Lock()
        self.fileInRes = []
        self.isRunning = False
        self.peerDownloadingFrom = []
        self.server = []

        # A socket for listening from other peers in the network
        self.peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peerSocket.bind((self.peerIP, self.portForPeer))

        print(f"A peer with IP address {self.peerIP}, ID {self.portForTracker} has been created")

        
        self.connected_client_conn_list = [] # Current clients conn connected to this client
        self.connected_client_addr_list = [] # Current clients addr connected to this client
        self.connected_tracker_conn_list = []
        self.connected_tracker_addr_list = []
        self.new_conn_thread_list = []

    @property # This creates an own respo for peer to save metainfo file
    def peerOwnRes(self):
        peerOwnRes = "my_own_respo_" + str(self.peerID)
        os.makedirs(peerOwnRes, exist_ok=True)
        peerOwnRes += "/"
        return peerOwnRes
    
    def getFileInRes(self) -> list:
        ownRespository = os.listdir("peer_respo")
        files = []
        if len(ownRespository) == 0:
            return files
        else: 
            for name in ownRespository:
                if(os.path.getsize("peer_respo/" + name) == 0):
                    os.remove("peer_respo/" + name)
                else:
                    files.append(File(self.peerOwnRes+name))


                    # # Testing creating metainfo
                    # file_obj = File("peer_respo/"+name)
                    # files.append(file_obj)
                    # # Get metainfo and save into a text file
                    # self.save_metainfo_to_txt(file_obj.meta_info)
        return files
    
    # def save_metainfo_to_txt(self, metainfo):
    #     # The path to txt file that saves metainfo of a specific file
    #     file_path = os.path.join(self.peerOwnRes, f"{metainfo.fileName}_metainfo.txt")
        
    #     # Write metainfo into file
    #     with open(file_path, "w", encoding="utf-8") as file:
    #         file.write(f"File Name: {metainfo.fileName}\n")
    #         file.write(f"File Length: {metainfo.length} bytes\n")
    #         file.write(f"Piece Length: {metainfo.pieceLength} bytes\n")
    #         file.write(f"Number of Pieces: {int(metainfo.numOfPieces)}\n")
    #         file.write(f"SHA-1 Hashes of Pieces: {metainfo.pieces.hex()}\n")
        
    #     print(f"Metainfo for {metainfo.fileName} has been saved to {file_path}")
    
    # List of clients connected to the Tracker
    def list_clients(self):
        if client_addr_list:
            print("Connected Clients:")
            for i, client in enumerate(client_addr_list, start=1):
                print(f"{i}. IP: {client[0]}, Port: {client[1]}")
        else:
            print("No clients are currently connected.")

    # List of peers connected to this client
    def list_peers(self):
        if self.connected_client_addr_list:
            print("Connected Peers:")
            for i, client in enumerate(self.connected_client_addr_list, start=1):
                print(f"{i}. IP: {client[0]}, Port: {client[1]}")
        else:
            print("No peers are currently connected.")

    def update_client_list(self, server_host, server_port):
        if (server_host, server_port) in self.connected_tracker_addr_list:
            index = self.connected_tracker_addr_list.index((server_host, server_port))
            conn = self.connected_tracker_conn_list[index]
        else:
            print(f"No connection found with Tracker {server_host}:{server_port}.")
            return

        # Create command for the Tracker
        header = "update_client_list:"
        message = header.encode("utf-8")
        conn.sendall(message)

        print(f"Client list requested to Tracker ({server_host}:{server_port}).")     

    # Connect to the Tracker
    def new_conn_tracker(self, tracker_socket, server_host, server_port):
        global client_addr_list
        print(f"Connected to Tracker ('{server_host}', {server_port}).")
        
        tracker_socket.settimeout(5)
        while not stop_event.is_set():
            try:
                data = tracker_socket.recv(4096)
                if not data:
                    break

                command = data[:(data.find(b":"))].decode("utf-8")
                if command == "update_client_list":
                    # Receive the clients list from the Tracker
                    client_addr_list = pickle.loads(data[len("update_client_list:"):])
                    print("Client list received.")
                elif command == "disconnect":
                    break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Client error: {e}")
                break

        tracker_socket.close()
        self.connected_tracker_conn_list.remove(tracker_socket)
        self.connected_tracker_addr_list.remove((server_host, server_port))
        print(f"Tracker ('{server_host}', {server_port}) disconnected.")

    def connect_to_tracker(self, server_host, server_port):
        try:
            tracker_socket = socket.socket()
            tracker_socket.connect((server_host, server_port))
        except ConnectionRefusedError:
            print(f"Could not connect to Tracker {server_host}:{server_port}.")

        # Send client port separately
        string_client_port = str(self.portForPeer)
        tracker_socket.sendall(string_client_port.encode("utf-8"))
        time.sleep(0.1) # SPE: neighbour sendall()

        # Create thread
        thread_tracker = Thread(target=self.new_conn_tracker, args=(tracker_socket, server_host, server_port))
        thread_tracker.start()
        self.new_conn_thread_list.append(thread_tracker)

        # Record the Tracker metainfo
        self.connected_tracker_conn_list.append(tracker_socket)
        self.connected_tracker_addr_list.append((server_host, server_port))
    
        self.update_client_list(server_host, server_port)

    def new_conn_peer(self, peer_socket, peer_ip, peer_port):
        print(f"Connected to peer {peer_ip}:{peer_port}.")

        peer_socket.settimeout(5)
        while not stop_event.is_set():
            try:
                data = peer_socket.recv(4096)
                if not data:
                    break

                command = data[:(data.find(b":"))].decode("utf-8")
                if command == "disconnect":
                    break
            except socket.timeout:
                continue
            except Exception:
                print("Error occured!")
                break

        peer_socket.close() #* Close the socket that connects with the corresponding peer
        self.connected_client_conn_list.remove(peer_socket) 
        self.connected_client_addr_list.remove((peer_ip, peer_port))
        print(f"Peer ('{peer_ip}', {peer_port}) removed.")

    # Connect to all peers
    def connect_to_all_peers(self):
        for peer in client_addr_list:
            if peer[0] == self.peerIP and peer[1] == self.portForPeer:
                continue
            self.connect_to_peer(peer[0], peer[1])
        print("All peers have been connected.")

    # Connect to one peer
    def connect_to_peer(self, peer_ip, peer_port):
        try:
            if peer_ip == self.peerIP and peer_port == self.portForPeer:
                print("Cannot connect to self.")
                return
            peer_socket = socket.socket()
            peer_socket.connect((peer_ip, peer_port))
        except ConnectionRefusedError:
            print(f"Could not connect to peer {peer_ip}:{peer_port}.")
    
        # Send peer port separately
        string_peer_port = str(peer_port)
        peer_socket.send(string_peer_port.encode("utf-8"))
        
        # Create thread
        thread_peer = Thread(target=self.new_conn_peer, args=(peer_socket, peer_ip, peer_port))
        thread_peer.start()
        self.new_conn_thread_list.append(thread_peer)

        # Record the new peer metainfo
        self.connected_client_conn_list.append(peer_socket)
        self.connected_client_addr_list.append((peer_ip, peer_port))

    def client_program(self):
        print(f"Peer IP: {self.peerIP} | Peer Port: {self.portForPeer}")
        print("Listening on: {}:{}".format(self.peerIP, self.portForPeer))
        
        self.peerSocket.settimeout(5)
        self.peerSocket.listen(10)

        while not stop_event.is_set():
            try:
                peer_socket, addr = self.peerSocket.accept() #* peer_socket is the socket to exchange data ( which is the port to connect to the other peer) with the connected peer, different from peerSocket which is only the socket for connecting with peers
                peer_ip = addr[0]

                # Receive peer port separately
                string_peer_port = peer_socket.recv(1024).decode("utf-8") #* Receive the port that the peer just connected with us sent us
                peer_port = int(string_peer_port) #* The port that the peer sent through socket

                # Create thread
                thread_peer = Thread(target=self.new_conn_peer, args=(peer_socket, peer_ip, peer_port)) 
                thread_peer.start()
                self.new_conn_thread_list.append(thread_peer)

                # Record the new peer metainfo
                self.connected_client_conn_list.append(peer_socket) #* Save each socket for connection with each peer
                self.connected_client_addr_list.append((peer_ip, peer_port)) #* Save the IP and the port of connected peer
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Peer error: {e}")
                break

        self.peerSocket.close()
        print(f"Peer {self.peerIP} stopped.")

    def disconnect_from_tracker(self, server_host, server_port):
        if (server_host, server_port) in self.connected_tracker_addr_list:
            index = self.connected_tracker_addr_list.index((server_host, server_port))
            conn = self.connected_tracker_conn_list[index]
        else:
            print(f"No connection found with Tracker {server_host}:{server_port}.")
            return

        header = "disconnect:"
        message = header.encode("utf-8")
        conn.sendall(message)

        print(f"Disconnect requested to Tracker ({server_host}:{server_port}).")
        
    def disconnect_from_peer(self, peer_ip, peer_port):
        if (peer_ip, peer_port) in self.connected_client_addr_list:
            index = self.connected_client_addr_list.index((peer_ip, peer_port))
            conn = self.connected_client_conn_list[index]
        else:
            print(f"No connection found with client {peer_ip}:{peer_port}.")
            return

        header = "disconnect:"
        message = header.encode("utf-8")
        conn.sendall(message)

        print(f"Disconnect requested to peer ('{peer_ip}', {peer_port}).")

    def disconnect_from_all_peers(self):
        for addr in self.connected_client_addr_list:
            self.disconnect_from_peer(addr[0], addr[1])

        print("All peers have been disconnected.")

    def shutdown_peer(self):
        stop_event.set()
        for nconn in self.new_conn_thread_list:
            nconn.join(timeout=5)
        print("All threads have been closed.") 


if __name__ == "__main__":
    my_peer = peer()
    try:
        peer_thread = Thread(target=my_peer.client_program)
        peer_thread.start()

        while True:
            command = input("Peer> ")
            if command == "test":
                print("The program is running normally.")
            elif command.startswith("connect_to_tracker"):
                parts = command.split()
                if len(parts) == 3:
                    server_host = parts[1]
                    try:
                        server_port = int(parts[2])
                        my_peer.connect_to_tracker(server_host, server_port)
                    except ValueError:
                        print("Invalid port.")
                else:
                    print("Usage: connect_tracker <IP> <Port>")
            elif command.startswith("disconnect_from_tracker"):
                parts = command.split()
                if len(parts) == 3:
                    server_host = parts[1]
                    try:
                        server_port = int(parts[2])
                        my_peer.disconnect_from_tracker(server_host, server_port)
                    except ValueError:
                        print("Invalid port.")
                else:
                    print("Usage: disconnect_from_tracker <IP> <Port>")
            elif command == "list_clients":
                my_peer.list_clients()
            elif command == "update_client_list":
                my_peer.update_client_list(server_host, server_port)
            elif command == "list_peers":
                my_peer.list_peers()   
            elif command.startswith("connect_to_peer"):
                parts = command.split()
                if len(parts) == 3:
                    peer_ip = parts[1]
                    try:
                        peer_port = int(parts[2])
                        my_peer.connect_to_peer(peer_ip, peer_port)
                    except ValueError:
                        print("Invalid port.")
                else:
                    print("Usage: connect_to_peer <IP> <Port>")
            elif command == "connect_to_all_peers":
                my_peer.connect_to_all_peers() 
            elif command.startswith("disconnect_from_peer"):
                parts = command.split()
                if len(parts) == 3:
                    peer_ip = parts[1]
                    try:
                        peer_port = int(parts[2])
                        my_peer.disconnect_from_peer(peer_ip, peer_port)
                    except ValueError:
                        print("Invalid port.")
                else:
                    print("Usage: disconnect_from_peer <IP> <Port>")
            elif command == "disconnect_from_all_peers":
                my_peer.disconnect_from_all_peers()  
            elif command == "exit":
                my_peer.disconnect_from_tracker(server_host, server_port)
                my_peer.disconnect_from_all_peers()
                print("Exiting Client Terminal.")
                break
            else:
                print("Unknown Command.")
    except KeyboardInterrupt:
        print("\nThe Client Terminal interrupted by user. Exiting Client Terminal...")
    finally:
        print("Client Terminal exited.")
    
    my_peer.shutdown_peer()
    peer_thread.join(timeout=5)
    sys.exit(0)