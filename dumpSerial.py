#coding:utf-8
import threading
import sys,getopt,time,os
from mySerial import * #

'''
2021-04-20 20.37.39
mySerial，serialPort里open方法，有一个读线程。

网口读，往串口写。
串口读，往网口写，
读的内容，往全局变量写。
如：
<R>xxx
<R>xxaere
<W>yyyyy

2021-04-21 17.11.32
将mySerial文件内，读的方法，都改成只读一个字节。
同时，根据波特率115200，将超时都改为0.0001秒。
decodeRead类，添加一个decode方法，一个字符一个字符的解释。

'''

listReadWrite = []
listReadWriteRaw = []
listReadWriteHex = []
readWriteCount = [0,0,0] #网口读计数，串口读计数，解码错误数

glDic = {'serToNetFlag':False} #默认不是串口转网络

def usage():
    info = '''
    2020-10-27 09.07.15
    -c : 串口号。
    -i : IP地址，默认：192.168.6.204
    -p : 端口，默认：9090
    '''

#网络收-串口发
def ethToSer(netSerial,comSerial):
    global listReadWrite
    global listReadWriteHex
    global readWriteCount
    dRead = decodeRead()
    while True:
        curRead = netSerial.read()
        if curRead != b'':
            comSerial.write(curRead)
            readWriteCount[0] += len(curRead)
            # print('E2S:',curRead)
            # result = dRead.toDecode(curRead)
            result = dRead.decode(curRead)
            if result != False and glDic['serToNetFlag'] == False:
                listReadWrite.append('<W>'+result.replace('\r','<LR>').replace('\n','<LN>'))
                listReadWriteRaw.append('<W>'+result)
                listReadWriteHex.append('<W>'+toHex(result))
        else:
            time.sleep(0.0001)
    
#串口收-网络发
def serToNet(netSerial,comSerial):
    global listReadWrite
    global listReadWriteHex
    dRead = decodeRead()
    while True:
        curRead = comSerial.getRead()
        if curRead != b'':
            netSerial.write(curRead)
            readWriteCount[1] += len(curRead)
            # print('S2E:',curRead)
            # result = dRead.toDecode(curRead)
            result = dRead.decode(curRead)
            if result != False and glDic['serToNetFlag'] == False:
                listReadWrite.append('<R>'+result.replace('\r','<LR>').replace('\n','<LN>'))
                listReadWriteRaw.append('<R>'+result)
                listReadWriteHex.append('<R>'+toHex(result))
        else:
            time.sleep(0.0001)

#对读到的内容进行解码。    
    
class decodeRead:
    def __init__(self):
        self.readByte = b''
        self.errorCount = 0
        self.codeType = ['gbk','gb18030','utf-8']
        
    def tryDecode(self,varByte):
        #print('try:',varByte)
        for curCode in self.codeType:
            try:
                return varByte.decode(curCode)
            except Exception as e:
                pass
        return False
        
    def toDecode(self,varByte):
        '''
        处理流程：
        如果tryDecode返回False。
        则进入单字节解码。
        每次处理一个字节，最多处理4个字节。使用不同的编码循环进行检测。
        定位出错位置，解码可以解码的部份。
        剩余部份，一位一位进行解码判断。
        1、1个字节，使用不同的编码进行检测。
            如果检测不通过，则再添加1个字节，最多一次检测4个字节。
        2、如果4个节字都检测不通过，则删除第1个节字（解码错误计数加1），再进行步骤1。
        '''    
        result = self.tryDecode(varByte)
        if result != False:
            return result
        
        curResult = ''
        i = 1
        while True:
            onePart = self.tryDecode(varByte[0:i])
            if onePart != False:
                #print('OK:',onePart)
                curResult = curResult + onePart
                varByte = varByte[i:]
                if len(varByte) == 0:
                    return curResult
                i = 1
            else:
                i = i + 1
                if i >= 5: #最多判断4个字符。
                    i = 1
                    varByte = varByte[1:]
                    self.errorCount = self.errorCount + 1
                    #print('addOneError')
                    continue
                    
                if i >= len(varByte) or len(varByte) == 0:
                    if len(curResult) != 0:
                        return curResult
                    return False
                #print('#',varByte)
                
    def decode(self,oneByte):
        """
        oneByte为单个字节，如果tryDecode返回False。
        则返回False，
        """
        self.readByte += oneByte
        onePart = self.tryDecode(self.readByte)
        if onePart != False:
            self.readByte = b''
            return onePart
            
        if len(self.readByte) >= 4:
            self.readByte = self.readByte[4:]
            self.errorCount += 4
            
        return False
        
    def getErrorPosition(self,theError):
        return theError.split('position ')[1].split(':')[0]
    
            
#写到文件
def writeToFile(curReadWriteList,theType):
    curTime = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
    if theType == 'ascii':
        fileName = 'dumpSerial-('+curTime+')ascii.txt'
    elif theType == 'hex':
        fileName = 'dumpSerial-('+curTime+')hex.txt'
    elif theType == 'raw':
        fileName = 'dumpSerial-('+curTime+')raw.txt'
        
    print('写入文件:',fileName)
    f = open(fileName,'w',encoding='utf-8')
    curWR = None #当前读写，如果连接两个或多个读，则归为一个读。
    while True:
        if len(curReadWriteList) == 0:
            time.sleep(0.01)
            continue
        curLine = curReadWriteList.pop(0)
        if curWR == None:
            curWR = curLine[0:3]
        elif curWR == curLine[0:3]:
            curLine = curLine[3:]
        else: #转读写
            curWR = curLine[0:3]
            #if theType == 'hex': #如果是hex文件，就添加换行。
            curLine = '\n'+curLine
            
        if theType in ['ascii','hex']:    
            curLine = myReplay(curLine,['','<LR>','<LN>'],'<LR>\n')
            curLine = curLine.replace('<LR><LN>','<LR><LN>\n')
            curLine = curLine.replace('0d 0a','0d 0a\n')
            curLine = curLine.replace('0d 0d ','0d ') #两个\n替换成一个。
            curLine = curLine.replace('<LR><LR><LN>','<LR><LN>')
        if theType in ['raw']:
            curLine = curLine.replace('\r','')
            
        f.write(curLine)
        # print(curLine.replace('\r','<lr>').replace('\n','<ln>'),end='')
        # print(curLine,end='')
        # sys.stdout.flush()
        f.flush()

#自定义替换，只匹配mStr，但是不匹配fStr+mStr或mStr+tStr。
def myReplay(varString,matchList,new):
    fStr = matchList[0]
    mStr = matchList[1]
    tStr = matchList[2]
    if (fStr != '' and varString.find(fStr+mStr) != -1) or (tStr != '' and varString.find(mStr+tStr) != -1):
        return varString
    return varString.replace(mStr,new)

#显示收发计数
def showCount():
    global readWriteCount
    curNetRead = 0
    curSerRead = 0
    while True:
        if curNetRead != readWriteCount[0] or curSerRead != readWriteCount[1]:
            print('网络->串口:写('+str(readWriteCount[0])+')|串口->网络:读('+str(readWriteCount[1])+')Error:'+str(readWriteCount[2])+'\r',end='')
            sys.stdout.flush()
            curNetRead = readWriteCount[0]
            curSerRead = readWriteCount[1]
        else:
            time.sleep(0.1)

#转成中文，从minicom文件中复制过来的。            
def toHex(varString):  
    result = ''
    theLen = len(varString)  
    for i in range(theLen):  
        the_vol = ord(varString[i])  
        the_hex = '%02x'%the_vol  
        result += the_hex + ' '   
    return result 

def setTitle(theTitle):
    try:
        if os.name == 'nt':
            osSystem("title " + theTitle)
        if os.name == 'posix':
            sys.stdout.write("\x1b]2;" + theTitle + "\x07")
    except Exception as e:
        print('Error in setTitle:', e)

def osSystem(cmd):
    try:
        return os.system(cmd)
    except Exception as e:
        print('Error in osSystem:', e)

"""
2021-05-11 16.58.52
-c:<com4>，本地真实的com口。
-i:<IP>，如果是0.0.0.0，则本地监听。
-p:<Port>，对端监听端口或本地监听的端口。
-f:<fileName>，这个功能已经没用。
-w:,真实的串口转网络功能，不写日志文件。

"""
version = '2021-05-12 21.04.32'

def main():
    varCom = 'com4'
    varIp = '192.168.6.204'
    varPort = 9090
    varFilaName = 'dumpSerialData.txt'
    alTime = '2021-06-18 17.01.57'
    theTitle = '串口截包工具 '
    
    setTitle(theTitle+alTime)

    opts, args = getopt.getopt(sys.argv[1:],"wi:p:f:c:",["help"])
    for op, value in opts:
        if op == "-c":
            varCom = str(value)
        if op == "-i":
            varIp = str(value)
        if op == '-p':
            varPort = int(value)
        if op == '-f':
            varFilaName = value
        if op == '-w':
            glDic['serToNetFlag'] = True
        if op == '-h' or op == '--help':
            usage()
            delay(10000)
    
    netSerial = serialNet(varIp,varPort)
    if netSerial.open() == True:
        print('网络开始连接：',varIp,':',varPort)
    #netSerOpt = serialFun(netSerial)

    comSerial = serialPort(varCom,baudrate=115200)
    if comSerial.open() == True:
        print('打开串口：',varCom,'成功。')
    else:
        print('打开串口：',varCom,'失败。')
        delay(10000)
    
    threading.Thread(target=ethToSer,args=(netSerial,comSerial,)).start() #网络到串口
    threading.Thread(target=serToNet,args=(netSerial,comSerial,)).start() #串口到网络

    if glDic['serToNetFlag'] == True:
        print('串口转网络模式，不写文件。')
    else:
        print('串口截包模式，写文件。')
        threading.Thread(target=writeToFile,args=(listReadWrite,'ascii',)).start()
        threading.Thread(target=writeToFile,args=(listReadWriteHex,'hex',)).start()
        threading.Thread(target=writeToFile,args=(listReadWriteRaw,'raw',)).start()    

    threading.Thread(target=showCount,args=()).start()

def test():
    c = b'<\xe2\x80\x9callgozwg@163.com\xe2\x80\x9d> Date'
    a = b'\xd9\xd8\xd8\xd9\xd8\xd1\xdc\xdb\xc7\xc4W\xa3\xd8\x82\xd0\x82\xd0\x86\xdc\xd9\xda\xd8'
    b = b'<\xe2\x80\x9callgozwg\xd9\xd8\xd8\xd9\xd8\xd1\xdc\xdb\xc7\xc4W\xa3\xd8\x82\xd0\x82\xd0\x86\xdc\xd9\xda\xd8@163.com\xe2\x80\x9d> Date'
    drObj = decodeRead()
    result = drObj.toDecode(b)
    print(result)
            
if __name__ == '__main__':
    main()
    #test()
