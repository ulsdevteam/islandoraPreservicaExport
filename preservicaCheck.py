import requests
import time

#generate token to access preservica restful api
sUrl="https://pitt.preservica.com/api/accesstoken/login"
testuser ="testuser@pitt.edu"
testpw="testpassword"
data ={"username": testuser,
        "password": testpw
               }
headers = {"Contnent-Type": "application/x-www-form-urlencoded"}
def generateToken():    
    r = requests.post (sUrl, data=data, headers=headers)
    if r.status_code != 200:
        print("Error:" , r.status_code)
        exit(1)
    else:
        return [r.json()['token'], r.json()['refresh-token']]
        

def getRefreshToken(s):
    sRefreshUrl ="https://pitt.preservica.com/api/accesstoken/refresh?refreshToken=" + s[1]
    newheaders = {"Preservica-Access-Token" : s[0],
                  "Contnent-Type": "application/x-www-form-urlencoded"}
    
    res = requests.post (sRefreshUrl, headers=newheaders)
    if res.status_code == 200:
        return [res.json()['token'], res.json()['refresh-token']]
