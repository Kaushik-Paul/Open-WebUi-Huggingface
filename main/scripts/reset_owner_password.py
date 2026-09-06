"""Offline owner recovery. Stop the web service and back up its database first."""
import asyncio
import getpass
import os
import sys

async def main():
    from open_webui.models.users import Users
    from open_webui.models.auths import Auths
    from open_webui.utils.auth import get_password_hash
    owner = await Users.get_user_by_email(os.environ['WEBUI_ADMIN_EMAIL'].strip().lower())
    if owner is None or owner.role != 'admin':
        raise SystemExit('Configured owner was not found')
    password = getpass.getpass('New owner password (12+ characters): ')
    if len(password) < 12 or password != getpass.getpass('Confirm password: '):
        raise SystemExit('Password too short or confirmation mismatch')
    if not await Auths.update_user_password_by_id(owner.id, await get_password_hash(password)):
        raise SystemExit('Password update failed')
    print('Password updated. Rotate WEBUI_SECRET_KEY and restart to invalidate existing JWT sessions.')

if __name__ == '__main__':
    asyncio.run(main())
