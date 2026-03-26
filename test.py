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