import socket
 
HOST = "192.168.0.101"
PORT = 23
 
def read_until_idle(sock, idle_timeout=1):
    """Lee datos hasta que no llegue nada durante idle_timeout segundos"""
    sock.settimeout(idle_timeout)
    full_response = ""
    
    try:
        while True:
            data = sock.recv(2048)
            if not data:
                break
            full_response += data.decode()
    except socket.timeout:
        pass  # Timeout significa que ya no hay más datos
    
    return full_response
 
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print("Connected to Palloran device console.")
    
    # Leer mensaje de bienvenida
    welcome = read_until_idle(s, idle_timeout=0.5)
    if welcome:
        print(welcome.strip())
 
    while True:
        cmd = input("> ")
        if cmd.lower() in ("exit", "quit"):
            break
 
        s.sendall((cmd + "\n").encode())
        
        # Leer toda la respuesta con un timeout más largo
        response = read_until_idle(s, idle_timeout=1.0)
        
        if response:
            print("Response:", response.strip())
        else:
            print("No response received")
 