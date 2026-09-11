import importlib.util
from pathlib import Path
import tempfile
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workbench',root/'workbench.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Stream:
    def __init__(self,lines): self.lines=iter(lines);self.sent=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def write(self,b):self.sent.append(b);return len(b)
    def readline(self,n):return next(self.lines).encode()
class Sock:
    def __init__(self,s):self.s=s
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def makefile(self,*args,**kwargs):return self.s
with tempfile.TemporaryDirectory() as d:
    m.BASE=Path(d);(m.BASE/'private').mkdir();(m.BASE/'private/control.token').write_text('a'*64)
    for final in ['USB_DONE','ABORTED_USB_OFF']:
        s=Stream(['WORKBENCH 1 AUTH_REQUIRED\n','OK AUTH\n',
          'STATUS mounted=1 usb=1 armed=0 last=0 txid=0 tx=IDLE max=512\n',
          'OK ARM ONE_ATTEMPT 30000ms\n','OK SUBMITTED\n',
          f'STATUS mounted=1 usb=1 armed=0 last=1 txid=1 tx={final} max=512\n'])
        with patch.object(m.socket,'create_connection',return_value=Sock(s)) as connect,patch('sys.argv',['workbench.py','--host','127.0.0.1','send','--hex','FD FA 08 FF 41 21 FE A2']):
            try:m.main()
            except SystemExit:assert final!='USB_DONE'
            assert connect.call_count==1
        assert sum(b.startswith(b'SEND ') for b in s.sent)==1
        assert s.sent[3]==b'SEND 1 fdfa08ff4121fea2\n'
    print('PASS client: exact bytes, one connection/one send, no retry on uncertain delivery')

# Logical clock: exercise long waits without sleeping or opening a real socket.
class Clock:
    def __init__(self):self.t=0.0
    def monotonic(self):return self.t
    def sleep(self,n):self.t+=n
class DelayedStream(Stream):
    def __init__(self,clock,finish,outcome='USB_DONE',advertised=90000,disconnect=None):
        super().__init__([]);self.clock=clock;self.finish=finish;self.outcome=outcome
        self.advertised=advertised;self.disconnect=disconnect;self.started=False;self.greeting=True
    def readline(self,n):
        if self.greeting:self.greeting=False;return b'WORKBENCH 1 AUTH_REQUIRED\n'
        if self.disconnect is not None and self.clock.t>=self.disconnect:return b''
        cmd=self.sent[-1]
        if cmd.startswith(b'AUTH '):return b'OK AUTH\n'
        if cmd==b'ARM\n':return b'OK ARM ONE_ATTEMPT 30000ms\n'
        if cmd.startswith(b'SEND '):self.started=True;return b'OK SUBMITTED\n'
        assert cmd==b'STATUS\n'
        state=('PENDING' if self.clock.t<self.finish else self.outcome) if self.started else 'IDLE'
        return f'STATUS mounted=1 usb=1 armed=0 last={int(self.started)} txid={int(self.started)} tx={state} max=512 tx_timeout_ms={self.advertised}\n'.encode()
with tempfile.TemporaryDirectory() as d:
    m.BASE=Path(d);(m.BASE/'private').mkdir();(m.BASE/'private/control.token').write_text('a'*64)
    for finish,outcome,disconnect,ok in [(20,'USB_DONE',None,True),(89.5,'USB_DONE',None,True),(90,'ABORTED_USB_OFF',None,False),(200,'PENDING',None,False),(20,'USB_DONE',7,False)]:
        c=Clock();s=DelayedStream(c,finish,outcome,disconnect=disconnect);failed=False
        with patch.object(m.socket,'create_connection',return_value=Sock(s)) as connect,patch.object(m.time,'monotonic',c.monotonic),patch.object(m.time,'sleep',c.sleep),patch('sys.argv',['workbench.py','--host','127.0.0.1','send','--hex','02 03 04 20 00 01 84 C3']):
            try:m.main()
            except SystemExit:failed=True
        assert failed!=ok,(finish,outcome,disconnect)
        assert sum(x.startswith(b'SEND ') for x in s.sent)==1 and connect.call_count==1
        assert c.t<=95.25
        if ok:assert c.t>=finish
        if disconnect is None and finish>=90:assert c.t>=90
    c=Clock();s=DelayedStream(c,0,advertised=90001)
    with patch.object(m.socket,'create_connection',return_value=Sock(s)),patch('sys.argv',['workbench.py','--host','127.0.0.1','send','--hex','02 03 04 20 00 01 84 C3']):
        try:m.main();raise AssertionError('Unsafe timeout accepted')
        except SystemExit:pass
    assert not any(x.startswith((b'SEND ',b'ARM')) for x in s.sent)
print('PASS client long window: 20s/89.5s delivery, 90s abort, 95s bound, 7s disconnect, no retry, invalid deadline rejected before ARM')
