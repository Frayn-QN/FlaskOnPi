#!/usr/bin/env python3
#-*- coding:utf-8 -*-

import signal
import PCF8591 as ADC
import RPi.GPIO as GPIO
import time
import math
makerobo_DO = 17        #烟雾传感器数字I/O口
makerobo_Buzz = 18      #有源蜂鸣器数字I/O口
GPIO.setmode(GPIO.BCM)  #引脚映射，采用BCM编码方式

def cleanup_handler(signum, frame):
    print("Received SIGTERM. Cleaning up...")
    raise KeyboardInterrupt
# 注册信号处理函数
signal.signal(signal.SIGTERM, cleanup_handler)

#初始化工作
def makerobo_setup( ):
	ADC.setup(0x48)						#设置PCF8591模块地址
	GPIO.setup (makerobo_DO,GPIO.IN)	#将烟雾传感器数字I/O口设置为输入模式
	GPIO.setup (makerobo_Buzz,GPIO.OUT)
	#将有源蜂鸣器数字I/O口设置为输出模式
	GPIO.output (makerobo_Buzz,1)
	#设置有源蜂鸣器为高电平，初始状态为关闭有源蜂鸣器鸣叫
    
#打印信息，打印出是否检测到烟雾信息
def makerobo_Print(x):
	if x == 1:		#安全
		print ('')
		print ('	******************')
		print ('	* Makerobo Safe~ *')
		print ('	******************')
		print ('')
	
	if x == 0:		#检测到烟雾
		print ('')
		print ('	************************')
		print ('	* Makerobo Danger Gas! *')
		print ('	************************')
		print ('')
        
#循环函数
def makerobo_loop( ):
	makerobo_status = 1						#定义状态值变量
	makerobo_count = 0						#定义计数器变量值
	while True:								#无限循环
		# print (ADC.read(0))					#获取AINO的模拟量值
        
		makerobo_tmp = GPIO.input(makerobo_DO)	#读取烟雾传感器数字I/O口值
		if makerobo_tmp != makerobo_status:		#判断状态是否发生改变
			makerobo_Print(makerobo_tmp)		#打印函数,打印出烟雾传感器信息
			makerobo_status = makerobo_tmp		#将当前状态值设置为比较状态值，避免重复打印
        
		if makerobo_status == 0:	#当检测到烟雾时
			makerobo_count += 1		#计数器值累计
			#高低电平交替变化，让蜂鸣器发声
			if makerobo_count % 2 == 0:		#进行求余处理,高位为1,低位为0 
			    GPIO.output(makerobo_Buzz, 1)
			else:
				GPIO.output(makerobo_Buzz, 0)
		else:
			GPIO.output(makerobo_Buzz, 1)
		#设置有源蜂鸣器为高电平，初始状态为关闭有源蜂鸣器鸣叫
			makerobo_count = 0		#计数器赋0
		time.sleep(0.2)				#延时200ms

#资源释放函数
def destroy():
	GPIO.output(makerobo_Buzz, 1)	#设置有源蜂鸣器为高电平,初始状态为关闭有源蜂鸣器鸣叫
	GPIO.cleanup()			#释放资源

#程序入口
if __name__ == '__main__':
	try:
		makerobo_setup( )	#初始化函数
		makerobo_loop( )	#循环函数
	except KeyboardInterrupt:	#当按下Ctrl+C时,将执行destroy()子程序
	    destroy() 			#资源释放
