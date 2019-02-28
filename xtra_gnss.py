#!/usr/bin/env python
# coding: utf-8

# In[4]:


import serial
import time
import re
from datetime import datetime
import subprocess
import os
import urllib.request


# In[5]:


#Generic AT
CR = '\r\n'
ENABLE_AT='ATE1'

#Filesystem AT commands
UPLOAD_FILE='AT+QFUPL'
DELETE_FILE='AT+QFDEL'
LIST_FILES='AT+QFLST'
LIST_FILES_RAM=bytes('AT+QFLST="RAM:*"\r\n','utf-8')

#GPS AT commands
GPS_ENGINE='AT+QGPS'
XTRA='AT+QGPSXTRA'
XTRA_TIME='AT+QGPSXTRATIME'
XTRA_DATA='AT+QGPSXTRADATA'
END_SESSION='AT+QGPSEND'


# In[6]:


def encode_AT(cmd,args=None):
    if args is not None:
        if args != '?':
            args='=' + args
        cmd=cmd + args
    cmd = cmd + '\r\n'
    return bytes(cmd,'utf-8')


# In[7]:


def send_AT(cmd,args=None):
    encoded=encode_AT(cmd,args)
    ser.write(encoded)
    rsp=parse_rsp()
    return rsp


# In[8]:


def parse_rsp():
    rsp=''
    while (rsp.find('OK')<0 and rsp.find('CONNECT')<0 and rsp.find('ERROR')<0):
        r=ser.read(ser.inWaiting()).decode('utf-8')
        rsp=rsp+r
    return rsp


# In[9]:


def send_file(filename,ramfs=False):
    
    with open(filename,"rb") as f:
        data=f.read()
        f.close()
        
    if ramfs:
        filename = "RAM:"+filename
        
    f_args='"' + filename + '"'
    s_args=str(len(data))
    args=f_args + ',' + s_args
    
    rsp = send_AT(UPLOAD_FILE,args)
    
    if rsp.find('ERROR')>-1:
        return rsp
    ser.write(data)
    rsp = rsp+parse_rsp()
    
    return rsp
    


# In[10]:


def enable_xtra():
    rsp=send_AT(XTRA,'1')
    global port
    global ser
    ser.close()
    ser=None
    
    process = subprocess.Popen(['disablePixieModem'], stdout=subprocess.PIPE)
    out, err = process.communicate()
    out = out.decode('utf-8')
    print(out)
    
    process = subprocess.Popen(['enablePixieModem'], stdout=subprocess.PIPE)
    out, err = process.communicate()
    out = out.decode('utf-8')
    print(out)
    
    print("Waiting for Modem, this can take a long time...")        
    while out.find("Quectel")<0:
        time.sleep(1)
        process = subprocess.Popen(['mmcli','-L'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = out.decode('utf-8')
    print("Modem ready at: ",out)
    
    ser=serial.Serial(port)
    ser.timeout=3
    
    print("Enabling AT Commands...")
    rsp=send_AT(ENABLE_AT)
    if rsp.find('OK')<0:
        return rsp
    
    send_AT(END_SESSION)
    if rsp.find('OK')<0:
        return rsp
    
    return rsp


# In[11]:


def configure_xtra_data():
    print("Configuring XTRA TIME")
    utctime=datetime.utcnow()
    formated_time = utctime.strftime("%Y/%m/%d,%T")
    rsp=send_AT(XTRA_TIME,'0,"' + formated_time + '",1,1,5')
    if rsp.find('OK')<0:
        return rsp
    
    print("Setting up XTRA DATA in Modem filesystem")
    rsp=send_AT(DELETE_FILE,'"*"')
    if rsp.find('OK')<0:
        return rsp
    
    rsp=send_file("xtra2.bin")
    if rsp.find('OK')<0:
        return rsp
    
    rsp=send_AT(XTRA_DATA,'"xtra2.bin"')
    
    return rsp
    
    


# In[12]:


def configure_xtra():
    rsp=send_AT(XTRA,'?')
    if rsp.find('QGPSXTRA: 1')>-1:
        print("XTRA already enabled...")
        return
    
    print("Enabling XTRA...")
    rsp = enable_xtra()
    if rsp.find('OK')<0:
        print("Errors occurred:")
        print(rsp)
        return rsp
    
    print("Configuring XTRADATA...")
    get_xtra_file()
    rsp=configure_xtra_data()
    if rsp.find('OK')<0:
        print("Errors occurred:")
        print(rsp)
        return rsp
    
    print("XTRA Ready...")


# In[13]:


def get_xtra_file():
    url='http://xtrapath1.izatcloud.net/xtra2.bin'
    filename='/home/pixiepro/xtra2.bin'
    if not os.path.isfile(filename):
        try:
            print("Downloading XTRA file")
            urllib.request.urlretrieve(url, filename)
        except Exception as e:
            print("Could not download xtra file.")
            print(str(e))
            return
    print("File downloaded.")
    return


# In[20]:


def check_valid_file():
    rsp=send_AT(XTRA_DATA,'?')
    match = re.search(r'\d{4}/\d{2}/\d{2}', rsp)
    xtradate = datetime.strptime(match.group(), '%Y/%m/%d').date()
    
    if (datetime.utcnow().date() - xtradate).days > 7:
        print("File expired, downloading again...")
        rsp=get_xtra_file()
        configure_xtra_data()
    else:
        print("File is valid...")
        
    print("XTRA Ready...")
    return rsp


# In[15]:


def configure_xtra_gnss():   
    global ser
    global port
    port='/dev/ttyUSB2'
    ser=serial.Serial(port)
    ser.timeout=3
    rsp=send_AT(ENABLE_AT)
    configure_xtra()
    time.sleep(3)
    check_valid_file()
    rsp=send_AT(GPS_ENGINE,'1,30,50,0,1')
    


# In[16]:


if __name__ == "__main__" and '__file__' in globals():
    configure_xtra_gnss()
    exit(0)

