#!/bin/bash

function server() {
python3 -c "
import socket
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 9999))
s.listen(1)
print('Waiting...')
c, a = s.accept()
print(f'Connected from {a}')
import time
total = 0
start = time.time()
while True:
    d = c.recv(1048576)
    if not d: break
    total += len(d)
elapsed = time.time() - start
print(f'{total/1024/1024:.1f}MB in {elapsed:.1f}s = {total/elapsed/1024/1024:.1f}MB/s')
c.close()
s.close()
"
}

function client() {     
python3 -c "
import socket, time
s = socket.socket()
s.connect(('192.168.1.15', 9999))
data = b'x' * 1048576
start = time.time()
for _ in range(100):  # send 100MB
  s.sendall(data)
elapsed = time.time() - start
print(f'100MB in {elapsed:.1f}s = {100/elapsed:.1f}MB/s')
s.close()
"
}