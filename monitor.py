#!/bin/env python3

from web3 import Web3
import smtplib
import datetime
import time
import socket
import configparser
import ovh
import sys
import json
import urllib


config = configparser.ConfigParser() # on relis la config pour qu'elle puisse etre changee en live
if not config.read('config.ini') :
    print ("Configuration file 'config.ini' not found or empty")
    sys.exit(2)


w3 = Web3(Web3.HTTPProvider(config['eth1']['host']))

DEBUG=True
LASTSMS=None
BALANCES = {}

def do_alert(cause, datas) :
    global LASTSMS, DEBUG
    if config['mail']['enabled'] == "1" :
        debug_print("Sending mail")
        mail_alert(cause, datas)
    if config['sms']['enabled'] == "1" :
        if LASTSMS != cause :
            debug_print("Sending sms")        
            sms_alert(cause, datas)
            LASTSMS = cause
        else :
            debug_print('Cause not changed. No resending SMS')
    

def mail_alert(cause, datas):
    sender = config['mail']['from']
    receivers = config['mail']['to']

    message = """From: Monitoring Ethereum <%s>
To: %s
Subject: Ethereum alert


A problem has occured on %s.    
Alert : %s
Datas : %s
    """ % (config['mail']['from'],config['mail']['to'],socket.getfqdn(),cause, datas)
    

    try:
        s = smtplib.SMTP( config['mail']['server'])
        s.login( config['mail']['login'], config['mail']['password'])
        s.sendmail(sender, receivers, message)         
        print ("Successfully sent email")
    except smtplib.SMTPException:
        print ("Error: unable to send email")


def sendSMS(dest,message) :
    client = ovh.Client('ovh-eu', application_key=config['sms']['appKey'], application_secret=config['sms']['appSecret'], consumer_key=config['sms']['consumerKey'])
    
    res = client.get('/sms')
    print(res)
    if len(res) == 0 :
        print("No ServiceName - Cancelling send")
        sys.exit(1)

    smsSender = res[0]
    url = '/sms/' + smsSender + '/jobs/'

    if type(dest) == list :
        receivers = dest
    else :
        receivers = [dest]
    
    r = client.post(url,
                    charset='UTF-8',
                    coding='7bit',
                    message=message,
                    noStopClause=False,
                    priority='high',
                    receivers=receivers,
                    senderForResponse=True,
                    validityPeriod=2880
    )
    print (json.dumps(r, indent=4)) # pour l'affichage du résultat de la transaction. 



        
def sms_alert(cause, datas) :
    msg = "ETH1 ALERT : %s ; Datas : %s" % (cause, datas)
    sendSMS(config['sms']['to'], msg)
    

        
def debug_print(msg) :
    if DEBUG :
        print("[%s] %s" % (datetime.datetime.now().isoformat(), msg))




def getResponse(url):
    operUrl = urllib.request.urlopen(url)
    if(operUrl.getcode()==200):
        data = operUrl.read()
        jsonData = json.loads(data)
    else:
        print("Error receiving data", operUrl.getcode())
    return jsonData

        
def check_state(cur,last) :
    if cur != last :
        if cur == "Ok" and last != None :
            debug_print("Retour a la normale")
            do_alert("Eth1 is back to normal state","Last state was " + last)
    return cur
            





last_state = None        
while True :
    curstate = "Ok"
    debug_print('TIC')
    try :        
        if w3.eth.syncing :
            do_alert("Eth1 Not Synced !", w3.eth.syncing)
            debug_print("Not synced")
            curstate = "No Synced"
            time.sleep(60)
        else :
            debug_print("Sync Ok")


        # Maintenant l'eth2
        si = ''
        for i in config['eth2']['indices'].split(',') :
            si = si + 'indices=%s&' %i
        debug_print(si)
        r = getResponse('http://localhost:3500/eth/v1alpha1/validators/balances?%s' % si)
        for b in r['balances'] :
            debug_print(b)
            if b['status'] != 'ACTIVE' :
                do_alert("Eth2 Validator not active !", str(b))
            if b['index'] not in BALANCES :
                BALANCES[b['index']] = b['balance']
            if BALANCES[b['index']] > b['balance'] :
                do_alert('Loosing ETHERS !!!!', str(b))
            BALANCES[b['index']] = b['balance']
    except Exception as e :
        debug_print("Exception has occured : %s - %s" % (e, e.args))
        do_alert(type(e).__name__, e.args)
        curstate = "Exception"        
        time.sleep(60)
    last_state = check_state(curstate, last_state)
    time.sleep(5)
        
