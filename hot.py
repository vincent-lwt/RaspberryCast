import time
import hashlib
import hmac

def generateAuth():
    st = round(time.time())
    exp = st + 10000
    auth = "st=" + str(st) +"~exp=" + str(exp) + "~acl=/*"
    string = auth

    secret = [
        0x05,
        0xfc,
        0x1a,
        0x01,
        0xca,
        0xc9,
        0x4b,
        0xc4,
        0x12,
        0xfc,
        0x53,
        0x12,
        0x07,
        0x75,
        0xf9,
        0xee
    ]

    key = ""
    for i in range(0, len(secret)):
        key += chr(secret[i])

    key = bytes(key, 'utf-8')
    string = bytes(string, 'utf-8')


    sig = hmac.new( key, string, hashlib.sha256 ).hexdigest()
    #print(sig)
    auth += "~hmac=" + sig
    return auth

if __name__ == "__main__":
    generateAuth()