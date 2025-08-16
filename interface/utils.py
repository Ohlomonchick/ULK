import hashlib

def get_pnet_password(user_password):
    return hashlib.md5((user_password + '42').encode()).hexdigest()[:8]