# dumpSerial
串口截包、真实串口转网络（支持server或client模式）
通过命令行参数，实现串口截包功能（之前有发过类似的）与真实串口转网络功能。
1、串口截包功能
就是连接虚拟串口与真实串口，在中间进行截包。

2、真实串口转网络功能
因为最近有这样的需求，所以就在原来的基本上弄了个这样的东西。
这个功能其实就是串口截包功能，去掉写文件功能。

![image](https://user-images.githubusercontent.com/49386775/124685555-129bdd80-df04-11eb-90fd-f9763eb1142d.png)

```
命令行参数说明：
-c:<com口>，真实串口，命令：com4
-i:<IP地址>，如果配置成0.0.0.0，则server模式，否则为client模式。
-p:<端口>，监听端口或主动连接的端口。
-f:<文件名>，具体写到哪个文件，这个参数已经没有用。
-w:，真实串口转网络功能，其实就是去掉写文件功能。
```
例子：

本地串口COM4转网络，client模式：
`dumpSerial.exe -p 10004 -i 192.168.6.200 -c com4 -w`

本地串口COM4转网络，server模式：
`dumpSerial.exe -p 10004 -i 0.0.0.0 -c com4 -w`

串口截包，client模式：
`dumpSerial.exe -p 10004 -i 192.168.6.200 -c com4`

串口截包，server模式：
`dumpSerial.exe -p 10004 -i 0.0.0.0 -c com4`
