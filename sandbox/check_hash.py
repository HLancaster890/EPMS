import hashlib, base64

pwd = b"MyP@ss1"
parts = "$pbkdf2-sha256$600000$DFsyqejL4A6sMZzjXmgtKO5q6n+Ao2QLrKF/6wVpn+8$e+RGLCf/zLm1XQosEkQuvme6z2N2qqkG2buIPGIaXY4".split("$")
salt_b64 = parts[3] + "=="
hash_b64 = parts[4] + "=="
salt = base64.b64decode(salt_b64)
expected = base64.b64decode(hash_b64)
dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, int(parts[2]))
print(f"Match: {dk == expected}")
