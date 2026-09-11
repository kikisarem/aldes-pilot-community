"""Single receive-only RAW collector. No USB commands or expiry timer."""
import argparse,datetime,fcntl,os,socket,time
from pathlib import Path


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--host',required=True)
 parser.add_argument('--log',type=Path,required=True)
 parser.add_argument('--port',type=int,default=8765)
 args=parser.parse_args()
 args.log.parent.mkdir(parents=True,exist_ok=True)
 with args.log.with_suffix('.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  while True:
   try:
    with args.log.open('ab',buffering=0) as out:
     def mark(message):
      out.write(('\n[collector] '+datetime.datetime.now().isoformat(timespec='seconds')+' '+message+'\n').encode())
     with socket.create_connection((args.host,args.port),timeout=10) as conn:
      conn.settimeout(30);mark('CONNECT receive_only')
      while True:
       data=conn.recv(65536)
       if not data:break
       out.write(data)
       if out.tell()>32*1024*1024:
        # Rotate only between received chunks. The next CONNECT boundary
        # prevents reconstruction across the intentional discontinuity.
        break
      mark('DISCONNECT')
     os.fsync(out.fileno())
    if args.log.stat().st_size>32*1024*1024:
     for number in range(3,0,-1):
      source=args.log.with_name(args.log.name+f'.{number}')
      if source.exists():
       if number==3:source.unlink()
       else:source.replace(args.log.with_name(args.log.name+f'.{number+1}'))
     args.log.replace(args.log.with_name(args.log.name+'.1'))
   except OSError as exc:
    with args.log.open('ab',buffering=0) as out:
     out.write(('\n[collector] ERROR '+str(exc)+'\n').encode())
   time.sleep(2)

if __name__=='__main__':main()
