"""Trusted local administration. No default passwords or public reset endpoints."""
import argparse
import getpass
import webbrowser
from app.config import Settings
from app.store import Store
from app.security import PASSWORDS, validate_password

def main():
    parser=argparse.ArgumentParser(description='RefundGuard local administration')
    parser.add_argument('action',choices=['setup-link','open','reset-password','reset-mfa','configure-openai','usage','backup','restore','verify-evidence'])
    parser.add_argument('--email')
    parser.add_argument('--output',type=__import__('pathlib').Path)
    parser.add_argument('--archive',type=__import__('pathlib').Path)
    parser.add_argument('--key-file',type=__import__('pathlib').Path)
    parser.add_argument('--destination',type=__import__('pathlib').Path)
    args=parser.parse_args()
    if args.action=='restore':
        from app.recovery import restore
        import json
        if not args.archive or not args.destination or not args.key_file:
            parser.error('restore requires --archive, --destination and --key-file')
        print(json.dumps(restore(args.archive,args.destination,args.key_file),indent=2))
        return
    settings=Settings.from_env()
    if args.action=='configure-openai':
        import os
        from pathlib import Path
        from dotenv import dotenv_values
        from app.config import ROOT
        path=ROOT/'.env'
        if path.is_symlink():
            parser.error('The environment file must not be a symlink')
        key=getpass.getpass('OpenAI API key (hidden; stored only in project/.env): ').strip()
        if not key.startswith('sk-') or len(key)<20:
            parser.error('That does not look like an OpenAI API key')
        values=dict(dotenv_values(path)) if path.exists() else {}
        values.update({'AI_PROVIDER':'openai','OPENAI_API_KEY':key,'OPENAI_MODEL':'gpt-5.6-luna',
                       'OPENAI_REASONING_EFFORT':'none','OPENAI_DAILY_BUDGET_USD':'1.00',
                       'OPENAI_MONTHLY_BUDGET_USD':'5.00','EMBEDDING_MODEL':'text-embedding-3-small'})
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(descriptor,'w') as f:
            for name,value in values.items():
                if value is not None:
                    value=value.replace('\\','\\\\').replace("'","\\'").replace('\n','\\n').replace('\r','\\r')
                    f.write(f"{name}='{value}'\n")
        os.chmod(path,0o600)
        print('Saved the private server key and conservative API budgets. Restart the local server to enable OpenAI.')
        print('For Railway, enter the key directly in Railway Variables; this file is excluded from deployments.')
        return
    settings.validate()
    store=Store(settings)
    if args.action=='backup':
        from app.recovery import backup
        import json
        if not args.output or not args.key_file:
            parser.error('backup requires --output and --key-file (keep the key separately)')
        print(json.dumps(backup(store,args.output,args.key_file),indent=2))
        return
    if args.action=='verify-evidence':
        import hashlib,hmac,json
        if not args.archive:
            parser.error('verify-evidence requires --archive')
        envelope=json.loads(args.archive.read_text())
        encoded=json.dumps(envelope['payload'],sort_keys=True,separators=(',',':')).encode()
        expected=hmac.new((store.path.parent/'evidence-key').read_bytes().strip(),encoded,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,envelope['signature']):
            parser.error('Evidence signature does not match')
        print('Evidence signature verified. Independently retain the snapshot and signing key.')
        return
    if args.action=='usage':
        import json
        from app.budget import Budget
        print(json.dumps(Budget(store).summary(),indent=2))
        return
    if args.action in ('open','setup-link'):
        token=store.bootstrap_token()
        url=settings.origin+('/#setup='+token if token else '/')
        if args.action=='open':
            webbrowser.open(url)
            print('Opened the workspace. First-time setup creates your private administrator account.')
        else:
            print(url)
        return
    if not args.email:
        parser.error('--email is required for account recovery')
    user=store.one('SELECT id FROM rg_users WHERE email=?',(args.email.strip().lower(),))
    if not user:
        parser.error('Account not found')
    if args.action=='reset-mfa':
        if input('Type RESET to revoke MFA and all sessions for this account: ')!='RESET':
            parser.error('Cancelled')
        with store.connect() as db:
            db.execute('DELETE FROM rg_mfa WHERE user_id=?',(user['id'],))
            db.execute('DELETE FROM rg_sessions WHERE user_id=?',(user['id'],))
        store.event('local-admin','auth.mfa_reset',target=user['id'])
        print('MFA reset; password unchanged, sessions revoked. Production privileged accounts must enroll again.')
        return
    password=getpass.getpass('New password (15–128 characters): ')
    validate_password(password)
    if password!=getpass.getpass('Confirm password: '):
        parser.error('Passwords did not match')
    with store.connect() as db:
        db.execute('UPDATE rg_users SET password_hash=? WHERE id=?',(PASSWORDS.hash(password),user['id']))
        db.execute('DELETE FROM rg_sessions WHERE user_id=?',(user['id'],))
    store.event('local-admin','auth.password_reset',target=user['id'])
    print('Password reset. All sessions for this account were revoked.')

if __name__=='__main__':
    main()
