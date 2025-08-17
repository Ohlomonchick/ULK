import hashlib

def get_pnet_password(user_password):
    return hashlib.md5((user_password + '42').encode()).hexdigest()[:8]


def get_pnet_lab_name(lab):
    return lab.slug + '_' + lab.lab_type.lower()