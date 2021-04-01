import socket
import ubinascii
import struct
import time
from uModBus.serial import Serial
from uModBus.tcp import TCP
import machine
from machine import Pin
from network import WLAN, LTE
import pycom

def blinkRGB(colour, sTimeOn, sTimeOff, reps, sPause):
    for x in range(reps):
        pycom.rgbled(colour) # colour
        time.sleep(sTimeOn)
        pycom.rgbled(0x000000) # OFF
        if x != reps-1:
            time.sleep(sTimeOff)
    time.sleep(sPause)

def disconnLTE():
    try:
        print('Disconnecting LTE...')
        lte.disconnect()
        while lte.isconnected():
            time.sleep(0.25)
        print('LTE disconnected')

        print('Dettaching LTE...')
        lte.dettach(reset = True)
        while lte.isattached():
            time.sleep(0.25)
        print('LTE dettached')
        return 1

    except Exception as e:
        print(e)
        blinkRGB(0x300000, 0.1, 0.1, 2, 0.3) # red
        return 0

def disableLTE():
    try:
        print('Disabling LTE...')
        lte.deinit(detach = True, reset = True)
        print('LTE disabled...')
        return 1

    except Exception as e:
        print(e)
        print('Cannot disable LTE')
        blinkRGB(0x300000, 0.1, 0.1, 2, 0.3) # red
        return 0

def connLTE():
    try:
        minToWait = 5
        print('Attaching to LTE, timeout set to', minToWait , 'm ...')
        lte.attach(apn="eplpwa.vodafone.iot")
        i = 0
        while not lte.isattached():
            time.sleep(0.25)
            blinkRGB(0x001510, 0.01, 0, 1, 0.01) # blueish
            if i > (minToWait*60*3):
                raise Exception('Cannot attach to LTE')
            i = i+1

        print('LTE attached')
        blinkRGB(0x003000, 0.1, 0, 1, 0.3) # green


        print('Connecting to LTE, timeout set to', minToWait , 'm ...')
        lte.connect()       # start a data session and obtain an IP address
        i = 0
        while not lte.isconnected():
            time.sleep(0.25)
            blinkRGB(0x001510, 0.01, 0, 1, 0.01) # blueish
            if i > (minToWait*60*3):
                raise Exception('Cannot connect to LTE')
            i = i+1
        print('LTE connected')
        blinkRGB(0x003030, 0.1, 0, 2, 0.3) # green

        return 1

    except Exception as e:
        print(e)
        print('LTE procedure failed')
        blinkRGB(0x300000, 0.1, 0.1, 2, 0.3) # red
        return 0

def regLTE():
    try:
        print('LTE network registration...')
        lte.send_at_cmd('AT+COPS=1,2,"23003"') # vodafone network registration
        lte.send_at_cmd('AT+CFUN=1') # full functionality
        print('LTE registred')

        return 1

    except Exception as e:
        print(e)
        blinkRGB(0x300000, 0.1, 0.1, 2, 0.3) # red
        return 0


######################### INITIALIZAZION #########################
print('Starting program...')
start = time.time()

print('Initial settings...')

pycom.heartbeat(False)
pycom.rgbled(0x003000) # green
p11_out = Pin('P11', mode=Pin.OUT) # set P11 as output
p11_out.value(0)

try:
    w = WLAN()
    w.deinit()
    print('WIFI off')
except Exception as e:
    print(e)
    print('WIFI off error - waiting 10 m and HW rebooting device')
    time.sleep(10*60)
    print('HW rebooting...')
    p11_out.value(1)
    time.sleep(10)

try:
    lte = LTE() # connecting to a modem
    print('LTE modem connected')
except Exception as e:
    print(e)
    print('LTE init error - waiting 10 m and HW rebooting device')
    time.sleep(10*60)
    print('HW rebooting...')
    p11_out.value(1)
    time.sleep(10)

pycom.rgbled(0x000000) # OFF

# RTU SERIAL MODBUS
uart_id = 0x01
modbus_obj = Serial(uart_id, pins=('P8', 'P9'), ctrl_pin='P10') # P8 = URART_OUT, P9 = URART_IN

# MODBUS SETTINGS
slave_addr=0x01
starting_address=0
register_quantity=1
signed=True

# SERVER ADDRESS SETTINGS
#server IP like ip = '192.168.0.1'
ip = ''
port = 3125

# DEVICE SETTINGS
devProject = 2
devType = 1
devAddr = 1
devStat = 0


######################### MAIN PROGRAM #########################

# READ HOLDING REGISTERS
tries = 10
for i in range(tries):
    try:
        print('Reading data over modbus', i,'- attempt...')
        register_value = modbus_obj.read_holding_registers(slave_addr, starting_address, register_quantity, signed)
        print('Holding register value: ' + ' '.join('{:d}'.format(x) for x in register_value))
        value = register_value[0]
        devStat = 1
        blinkRGB(0x003000, 0.1, 0, 1, 0.3) # green

    except Exception as e:
        print(e)
        value = -1
        devStat = 2
        blinkRGB(0x300000, 0.1, 0, 1, 0.3) # red

    if devStat == 1:
        break

    if i == tries-1:
        value = -1
        devStat = 2
        break

    time.sleep(2)

# CONNECTING TO LTE NETWORK

if(regLTE() != 1):
    disableLTE()
    blinkRGB(0x300030, 0.1, 0, 1, 0.3) # purple
    print('Waiting 1 m and HW rebooting device')
    time.sleep(1*60)
    print('HW rebooting...')
    p11_out.value(1)
    time.sleep(10)

if(connLTE() != 1):
    disconnLTE()
    disableLTE()
    blinkRGB(0x300030, 0.1, 0, 1, 0.3) # purple
    print('Waiting 1 m and HW rebooting device')
    time.sleep(1*60)
    print('HW rebooting...')
    p11_out.value(1)
    time.sleep(10)

# SEND DATA OVER LTE
try:
    addr = socket.getaddrinfo(ip, port)[0][-1]
    s = socket.socket()

    print('Sending data...')
    s.connect(addr)

    # BUILDING A MESSAGE
    frame = bytearray()
    # head
    headList = [devProject, devType, devAddr, devStat]
    # data
    if devStat==1:
        headList.append(1) # data type
        frame = bytearray(headList)
        frame += (value.to_bytes(4, "little"))
    else:
        frame = bytearray(headList)

    print('Full frame:')
    print(frame)

    s.send(frame)

    s.close()
    blinkRGB(0x0000ff, 0.1, 0.1, 1, 0.3) # blue
    print('Data sent')

except Exception as e:
    print(e)
    blinkRGB(0x300000, 0.1, 0.1, 2, 0.3) # red

# DISCONNECTING FROM LTE NETWORK
disconnLTE()
disableLTE()

# GO TO DEEPSLEEP
sleepTimeHours = 0
sleepTimeMinutes = 30
sleepTimeSeconds = 0
sleepTime = (3600*sleepTimeHours + 60*sleepTimeMinutes + sleepTimeSeconds)*1000

duration = (time.time() - start)*1000

if (sleepTime - duration < 0):
    sleepTime = 500
else:
    sleepTime= sleepTime - duration

print('It took %d s to execute the program.' % (duration/1000))

print('Demanded sleeping %d h, %d m, %d s.' % (sleepTimeHours, sleepTimeMinutes, sleepTimeSeconds))
print('Puting into sleep for %d s...' % (sleepTime/1000))
print('')

blinkRGB(0x300030, 0.1, 0, 1, 0.3) # purple
machine.deepsleep(sleepTime)
