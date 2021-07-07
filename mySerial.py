#coding:utf-8
import serial
import serial.tools.list_ports
import time,sys
import chardet #判断字符编码
import socket,threading
from serial import win32

'''
2020-7-31 11:30:40
重写串口类，实现：
1、具体方法与之前的实现的方法名相同。
2、支持真实串口与TCP远程主动或被动连接。

serialNet，这个是针对串口服务器用的。

没有解决的问题：
1、如果一直没有\r\n等出现，接收会一直阻塞。此时采用判断接收字节长度。

win10,OS 版本:          10.0.18363 暂缺 Build 18363
观察发与，大概1分钟发1次arp。

真实串口read，支持读取一个字节的参数。

2021-05-10 08.51.30
修改serialNet允许接受多个连接。
再修改ifFind，判断的字符使用gb2312进行编码后,再匹配。

'''

var_baud = {
'600':600,
'1200':1200,
'1800':1800,
'2400':2400,
'4800':4800,
'7200':7200,
'9600':9600,
'19200':19200,
'38400':38400,
'57600':57600,
'115200':115200,
'230400':230400,
'460800':460800,
'921600':921600
}

#数据位
var_data_bits = {
'5':serial.FIVEBITS,
'6':serial.SIXBITS,
'7':serial.SEVENBITS,
'8':serial.EIGHTBITS
}
#停止位
var_stop_bits = {
'1':serial.STOPBITS_ONE,
'2':serial.STOPBITS_TWO
}
#校验
var_parity = {
'None':serial.PARITY_NONE,
'Even':serial.PARITY_EVEN,
'Odd':serial.PARITY_ODD,
'Mark':serial.PARITY_MARK,
'Space':serial.PARITY_SPACE
}

#这个官方手册没有。
var_cts_rts = {
'On':0x03,
'Off':0x00
}

var_xon_xoff = {
'On':serial.XON,
'Off':serial.XOFF
}

#这个官方手册没有。
var_dtr_rts = {
'On':1,
'Off':0
}

#解码
def myDecode(varString):
    if len(varString) == 0:
        return ''
    # curCode = chardet.detect(varString)['encoding']
    # if curCode == None:
        # curCode = 'gbk'
    # print(chardet.detect(varString))
    try:
        return varString.decode('gb2312')
    except Exception as e:
        print('###############:',varString,e)
        return ''

class serialNet:
    def __init__(self,ip,port,inputSocket=None):
        self.ip = ip
        self.port = port
        self.exitFlag = False #close改变标志。

        self.inputSocket = inputSocket
        if self.inputSocket == None: #如果没有传入socket，则socket由对象自己解决。
            self.s = None #客户端
        else:
            self.s = self.inputSocket

        self.socket = None #服务端
        self.threadFlag = False #线程是否退出。
        self.recvList = [] #用来保存接收到的数据。
    
    def reconnect(self):
        """连接网络
        如果ip地址是0.0.0.0，则被动连接（只接受一个连接，第一个连接。）。
        如果ip地址不是0.0.0.0，则主动连接。
        在网络断开时，会主动重连。
        """
        connectCount = 0
        if self.ip == '0.0.0.0':
            '被动连接'
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.ip,self.port))
            self.socket.listen(4)
            self.socket.settimeout(1)
            
            while self.exitFlag == False:
                if self.s == None: #如果连接断开。
                    try:
                        self.s,self.address = self.socket.accept()
                    except socket.timeout as e:
                        self.s = None
                        self.address = None
                    except Exception as e:
                        self.s = None
                        print('#',connectCount,' Error in reconnect server:',self.ip,self.port,e,end=' \r')
                        connectCount += 1
                        time.sleep(0.1)
                else:
                    time.sleep(1)
                            
        else: #主动连接。
            while self.exitFlag == False:
                if self.s == None: #如果连接断开。
                    try:
                        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.s.settimeout(3)
                        self.s.connect((self.ip, self.port))
                        
                        #开启keepalive，无数据10秒后开始，间隔6秒，检测3次。
                        # self.s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        # self.s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 10)
                        # self.s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 6)
                        # self.s.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 3)
                        
                    except Exception as e:
                        self.s = None
                        print('#',connectCount,' Error in reconnect client:',self.ip,self.port,e,end=' \r')
                        connectCount += 1
                        time.sleep(1)
                else:
                    time.sleep(1)

    def startThread(self):
        if self.inputSocket == None:
            print('In socket inside mode.')
            threading.Thread(target=self.reconnect,args=()).start()

        threading.Thread(target=self.ss,args=()).start()
        self.threadFlag = True

    def open(self):
        self.exitFlag = False
        if self.threadFlag == False:
            self.startThread()
            
        time.sleep(0.2)
        if self.s == None:
            return False
        return True
    
    def close(self):
        self.exitFlag = True
        self.threadFlag = False
        self.s.close()
        self.s = None
        
    def flushInput(self):
        del self.recvList[:]
    
    def flushOut(self): #没有此功能。
        pass
    
    def listPort(self): #没有此功能。
        pass
    
    #如果在超时时间内，不断接收到数据时。持续接收。
    #....xx....xxx...xxxxx....xx..
    
    def ss(self):
        """
        接收线程，115200，大概每秒钟10K=10000字节。
        每个字节大概是0.1ms（实际上小于0.1ms），
        所以字符之间的超时，设置为0.0001秒。
        """
        timeout = 0.0001 #字符间隔超时
        while True:
            if self.exitFlag == True:
                return None
        
            if self.s == None:
                time.sleep(0.1)
                continue

            curRecv = b''
            self.s.settimeout(timeout)
            tmp = b''
            timeoutCount = 0
            while True:
                try:
                    tmp = self.s.recv(1029) #xmodem当中，1029或133
                except socket.timeout as e:
                    timeoutCount += 1
                    if timeoutCount > 60000:
                        # print('timeout',time.time())
                        # timeoutCount = 0
                        self.s.close()
                        self.s = None
                        break
                    continue
                    
                except Exception as e:
                    self.s = None
                    break
                
                timeoutCount = 0
                if len(tmp) != 0:
                    self.addToRecvList(tmp)
                    tmp = b''
                else: #如果被连接，连接被动断开，recv不会有错误，但是recv会马上返回空的字符串。
                    self.s = None
                    break
                #if curRecv[-2:] == b'\r\n' or curRecv[-1:] == b'\n' or curRecv.find(b'\r') != -1 or len(curRecv) >=1024:
                # if len(curRecv) >=1024:
                    # self.addToRecvList(curRecv)
                    # curRecv = b''
    #保存最新的数据。
    def addToRecvList(self,curRecv):
        if len(self.recvList) >= 2048:
            self.delFirstIndex()
        else:
            self.recvList.append(curRecv)
        # try:
            # curDecodeString = myDecode(curRecv)
            # self.recvList.append(curDecodeString)
        # except Exception as e:
            # print('Error in addToRecvList:',e)
    
    #返回类型为byte，不在这里进行延时。
    def read(self):
        if len(self.recvList) != 0:
            return self.recvList.pop(0)
        else:
            #time.sleep(0.01)
            return b''
        
    def delFirstIndex(self):
        try:
            del self.recvList[0]
        except Exception as e:
            pass
        
    def write(self,varString):
        if self.s == None:
            return False
            
        try:
            if type(varString) == type(b''):
                self.s.sendall(varString)
            else:
                self.s.sendall(varString.encode('gb2312'))
            #time.sleep(0.01)
            return True
        except socket.timeout as e:
            pass
        except Exception as e:
            print('Error in net write:',e)
            self.s = None
            return False

class serialPort:
    def __init__(self,port=None,
                 baudrate=9600,
                 bytesize=8,
                 parity=None,
                 stopbits=1,
                 timeout=0.0001, #超时时间，跟回netSerial里面ss的说明。
                 xonxoff=0,
                 rtscts=0,
                 interCharTimeout=None
                 ):

        self.port = port
        self.baudrate = baudrate
        self.bufferRead = [] #读缓存
        self.bytesize = var_data_bits[str(bytesize)]
        self.parity = var_parity[str(parity)]
        self.stopbits = var_stop_bits[str(stopbits)]
        self.timeout = timeout
        self.xonxoff = xonxoff
        self.rtscts = rtscts
        self.interCharTimeout = interCharTimeout #字符间隔超时
        self.closeFlag = False #退出标志。

    def open(self):
        # self._overlapped_read = win32.OVERLAPPED()
        # self._overlapped_read.hEvent = win32.CreateEvent(None, 1, 0, None)
        try:
            self.ser = serial.Serial(port = str(self.port),
                        baudrate = self.baudrate,
                        bytesize = self.bytesize,
                        parity = self.parity,
                        stopbits = self.stopbits,
                        timeout = self.timeout,
                        xonxoff = self.xonxoff,
                        rtscts = self.rtscts,
                        dsrdtr = False,
                        interCharTimeout = self.interCharTimeout)
            self.flushInput()
            self.flushOutput()
            threading.Thread(target=self.thrRead,args=()).start() #读线程
            return True
        except Exception as e:
            print('Error in open:',e)
            return False

    def isOpen(self):
        return  self.ser.isOpen()

    def flushInput(self):
        self.ser.flushInput()
    
    def flushOutput(self):
        self.ser.flushOutput()

    '''返回格式如下：
    [['Ok', 'COM13', 'NEOWAY HS-USB Diagnostics 8241 (COM13)'], 
    ['Ok', 'COM12', 'NEOWAY HS-USB TTY2 8241 (COM12)'], 
    ['Ok', 'COM14', 'NEOWAY HS-USB TTY1 8241 (COM14)'], 
    ['No', 'COM6', 'Prolific USB-to-Serial Comm Port (COM6)']]
    '''
    def listPort(self):
        portList = []
        curPortList = list(serial.tools.list_ports.comports())
        if len(curPortList) <= 0:
            return portList

        for onePort in curPortList:
            curSer = serial.Serial()
            curSer.port = onePort[0]
            curSer.baudrate = 115200
            try:
                curSer.open()
                if curSer.isOpen() == True:
                    portList.append(['Ok', onePort[0], str(onePort[1])])
                    curSer.close()
            except Exception as e:
                portList.append(['No', onePort[0], str(onePort[1])])
                curSer.close()

        return portList

    def close(self):
        self.flushInput()
        self.flushOutput()
        self.closeFlag = True
        time.sleep(1)
        self.ser.close()

    #读原始数据
    def rawRead(self):
        curRead = self.ser.read(1024)
        if len(curRead) == 0:
            return b''
        return curRead

    #读行，返回decode后的数据。
    def read(self,bit=None):
        if bit == None:
            curLine = self.ser.readline()
        else:
            curLine = self.ser.read(bit)
            
        if len(curLine) == 0:
            return ''
        return myDecode(curLine)
    
    #直接回存类型为byte
    def thrRead(self):
        curRecv = b''
        while self.closeFlag == False:
            tmpRecv = self.ser.read(1) #这里由1024改为1
            if len(tmpRecv) == 0:
                continue
            else:
                self.bufferRead.append(tmpRecv)
                
            # curRecv = curRecv + tmpRecv
            # result = self.checkDecode(curRecv)
            # if result != False:
                # self.bufferRead.append(result)
                # curRecv = b''    
        print('Exit thrRead.')
    
    #返回类型为byte    
    def getRead(self):
        if len(self.bufferRead) != 0:
            return self.bufferRead.pop(0)
        else:
            return b''
    
    def readline(self):
        theLine = self.ser.readline()
        if theLine == "":
            return ""
        return theLine.decode("gb2312")

    def write(self,varString):
        try:
            if type(varString) == type(b''):
                self.ser.write(varString)
            else:
                self.ser.write(varString.encode('gb2312'))
            self.flushOutput()
        except Exception as e:
            print('Error in write:',e)
            return False

    def checkDecode(self,varString,codeType = 'gb2312'):
        try:
            return varString.decode(codeType)
        except Exception as e:
            #print('Error in checkDecode',e)
            return False
    
    def getMode(self):
        #print('设备：'.rjust(7),self.ser.name)  # 设备名字
        print('端口：'.rjust(7),self.ser.port)  # 读或者写端口
        print('波特率：'.rjust(7),self.ser.baudrate)  # 波特率
        print('字节：'.rjust(7),self.ser.bytesize)  # 字节大小
        print('校验位：'.rjust(7),self.ser.parity)  # 校验位
        print('停止位：'.rjust(7),self.ser.stopbits)  # 停止位
        print('读超时：'.rjust(7),self.ser.timeout)  # 读超时设置
        print('写超时：'.rjust(7),self.ser.writeTimeout)  # 写超时
        print('xonxoff：'.rjust(7),self.ser.xonxoff)  # 软件流控
        print('rtscts：'.rjust(7),self.ser.rtscts)  # 软件流控
        print('dsrdtr：'.rjust(7),self.ser.dsrdtr)  # 硬件流控
        print('字符间隔超时：',self.ser.interCharTimeout)  # 字符间隔超时

class serialFun:
    def __init__(self,theObj):
        self.theObj = theObj
    
    def sendExpect(self,sendString='',expString='',allTime=10,pr=False,prN=False):
        if pr : print('##sendExpect:',repr(sendString),repr(expString),'timeout:',allTime,'##')
        if len(sendString) != 0:
            self.theObj.write(sendString)
        startTime = time.time()
        resultText = [] #记录所有的输出
        while time.time() - startTime < allTime:
            result = self.theObj.read()
            resultText.append(result)
            if pr : self.print(result)
            if prN : self.print('>('+str(len(result))+'):'+result[0:14])
            if self.ifFind(result,expString) == True:
                return (True,result)
                
        return (False,resultText)

    def loopSendExpect(self,sendString='',expString='',allTime=10,pr=False):
        startTime = time.time()
        while time.time() - startTime < allTime:
            if self.sendExpect(sendString,expString,allTime=1,pr=pr)[0] == True:
                return True
        return False

    def expectSend(self,expString='',sendString='',allTime=10,pr=False,prN=False):
        if pr : print('###expectSend:',repr(expString),repr(sendString),'time:',allTime,'###')
        self.theObj.flushInput()
        startTime = time.time()
        resultText = []
        while time.time() - startTime < allTime:
            result = self.theObj.read()
            resultText.append(result)
            if pr : self.print(result)
            if prN : self.print('>('+str(len(result))+'):'+result[0:14])
            if self.ifFind(result,expString) == True:
                self.theObj.write(expString)
                return (True,result)
        return (False,resultText)
        
    def ifFind(self,recvString,expString):
        if expString == '': #空，即不进行匹配。
            return False
        if type(expString) == type([]): #如果是list:
            for one in expString:
                if self.ifFind(recvString,one) == True:
                    return True
            return False
        else: #不是list
            if recvString.upper().find(expString.encode('gb2312').upper()) != -1:
                return True
            return False
    
    def print(self,varString):
        print(varString,end='')
        sys.stdout.flush()

def delay(timeout):
    startTime = time.time()
    leftTime = timeout
    while time.time() - startTime < timeout:
        print('>',round(leftTime,1),'\t\t\r',end='')
        sys.stdout.flush()
        leftTime = leftTime - 0.1
        time.sleep(0.1)

def main():
    # theSer = serialNet('192.168.0.24',9090)
    theSer = serialPort(port='com4',baudrate=115200)
    if theSer.open() == False:
        print('打开串口失败')
        return False
    # delay(4)
    # theSer.close()
    # delay(4)
    optSer = serialFun(theSer)
    resultFlag,resultText = optSer.sendExpect('login 0 admin 12345678\r\n','success',2)
    print(resultFlag)
    theSer.close()
    time.sleep(10000)
    
    while True:
        optSer.expectSend('login','\r\n',allTime=20,pr=True,prN=True)
        if optSer.sendExpect('\r\n','login',pr=True)[0] and optSer.sendExpect('login 1 config hr,123456\r\n','#',pr=True)[0]:
            print('登录成功。。')
            optSer.sendExpect('slog\r\n','',pr=True)
            optSer.loopSendExpect('slog\r\n','',allTime=1000,pr=True)
            theSer.close()
            return None
        
        #theSer.write('中文测试')
        #theSer.write('中文测试，china、\r\n')
    time.sleep(10000)

def main2():
    theSer = serialPort(port='com4',baudrate=115200)
    if theSer.open() == False:
        print('打开串口失败')
        return False
    time.sleep(4)
    theSer.write('\r\n')
    time.sleep(4)
    print(theSer.getRead())
    theSer.close()
    print('close......')

if __name__ == '__main__':
    main()