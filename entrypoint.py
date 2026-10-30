"""Container startup: mounted-volume permissions, dynamic port, and one worker."""
import os
from pathlib import Path
import sys

def command(environ):
    port=int(environ.get('PORT','8000'))
    if not 1<=port<=65535:
        raise ValueError('PORT must be between 1 and 65535')
    proxy_ips=environ.get('TRUSTED_PROXY_IPS','*' if environ.get('RAILWAY_PROJECT_ID') else '127.0.0.1')
    return [sys.executable,'-m','uvicorn','app.main:app','--host','0.0.0.0',
            '--port',str(port),'--workers','1','--limit-concurrency','64',
            '--timeout-keep-alive','5','--proxy-headers','--forwarded-allow-ips',proxy_ips]

def main():
    os.umask(0o077)
    database=Path(os.getenv('DATABASE_PATH','/data/refundguard.sqlite3'))
    if database.parent.is_symlink():
        raise RuntimeError('Database directory must not be a symlink')
    database.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.geteuid()==0:
        import pwd
        account=pwd.getpwnam('appuser')
        os.chown(database.parent,account.pw_uid,account.pw_gid)
        os.chmod(database.parent,0o700)
        for path in (database,Path(str(database)+'-wal'),Path(str(database)+'-shm'),database.parent/'setup-token',
                     database.parent/'mfa-key',database.parent/'evidence-key',database.parent/'backup-key'):
            if path.is_symlink():
                raise RuntimeError('Database files must not be symlinks')
            if path.exists():
                os.chown(path,account.pw_uid,account.pw_gid,follow_symlinks=False)
                os.chmod(path,0o600)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    args=command(os.environ)
    os.execv(sys.executable,args)

if __name__=='__main__':
    main()
