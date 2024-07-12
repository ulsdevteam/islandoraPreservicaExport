import requests
import getopt, sys
from getpass import getpass

#generate token to access preservica restful api
sUrl="https://pitt.preservica.com/api/accesstoken/login"
headers = {"Contnent-Type": "application/x-www-form-urlencoded"}

def generateToken():  
    #retrieve login credentials
    testusr = getpass("Please enter login: ")
    testpw =getpass("Please enter password: ")
    if (testpw and testusr):
        sdata ={
            "username": testusr,
            "password": testpw
            }
         #retrieve token    
        r = requests.post (sUrl, data=sdata, headers=headers)
        if r.status_code != 200:
            print("Error:" , r.status_code)
            sys.exit(-1)
        else:
            return [r.json()['token'], r.json()['refresh-token']]

def getRefreshToken(s):
    sRefreshUrl ="https://pitt.preservica.com/api/accesstoken/refresh?refreshToken=" + s[1]
    newheaders = {"Preservica-Access-Token" : s[0],
                  "Contnent-Type": "application/x-www-form-urlencoded"}
    
    res = requests.post (sRefreshUrl, headers=newheaders)
    if res.status_code == 200:
        return [res.json()['token'], res.json()['refresh-token']]
