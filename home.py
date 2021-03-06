'''
fixme 老的主程序 未采用Blueprint的版本
'''

from flask import Flask,render_template,request,redirect, url_for, flash, session, send_from_directory,send_file
from flask_bootstrap import Bootstrap
import random,datetime
from functools import wraps
import time
import functools
import os
from werkzeug.utils import secure_filename
import csv
import pandas as pd
import numpy as np
from struct import pack, unpack_from # Pylogix 结构体解析

'''
西门子库文件 python-snap7
'''
# import s7read
from snap7 import *
import snap7.client as client
from snap7.util import *
from snap7.snap7types import *

'''
罗克韦尔AB Pylogix 0.6.2
'''
from pylogix import *
from pylogix import PLC

class Timer(object):

    def __init__(self, data):
        self.PRE = unpack_from('<i', data, 6)[0]
        self.ACC = unpack_from('<i', data, 10)[0]
        bits = unpack_from('<i', data, 2)[0]
        self.EN = get_bit(bits, 31)
        self.TT = get_bit(bits, 30)
        self.DN = get_bit(bits, 29)

class Motion(object): # Su 仿照Timer类型添加Motion类型 ToDo

    def __init__(self, data):
        self.PRE = unpack_from('<i', data, 6)[0]
        self.ACC = unpack_from('<i', data, 10)[0]
        bits = unpack_from('<i', data, 2)[0]
        self.EN = get_bit(bits, 31)
        self.TT = get_bit(bits, 30)
        self.DN = get_bit(bits, 29)

def get_bit(value, bit_number):
    '''
    Returns the specific bit of a word
    '''
    mask = 1 << bit_number
    if (value & mask):
        return True
    else:
        return False

'''
倍福库文件 PyADS
'''
# todo
'''
opcua库文件 
'''
# todo
'''
influxDB 库文件
'''
from influxdb_client import InfluxDBClient,Point
# from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import random
import time

########登陆信息 暂时使用 还没启用数据库管
users = [
    {
        'username': 'root',
        'password': 'root'
    },
    {
        'username': 'username',
        'password': 'password'
    }
]

app = Flask(__name__)
Bootstrap(app)

## 设置密钥可以有效防止跨站请求伪造的攻击
app.config['SECRET_KEY'] = 'myproject'
app.secret_key = 'myproject'

############ 登陆验证 不登陆无法进入其它页面 ###################
def is_login(f):
    """用来判断用户是否登录成功"""
    # 保证函数在加了装饰器之后返回的不是wrapper函数名，而是原函数名

    @functools.wraps(f)
    def inner(*args, **kwargs):
        # 判断session对象中是否有seesion['user'],
        # 如果包含信息， 则登录成功， 可以访问主页；
        # 如果不包含信息， 则未登录成功， 跳转到登录界面;
        # next_url = request.path
        if session.get('user', None):
            return f(*args, **kwargs)
        else:
            # flash('用户必须登陆才能访问%s' % f.__name__)
            return redirect(url_for('home'))##返回首页 url_for 调用的是函数名
    return inner 
#################################################################

@app.route("/")
def home():
    return render_template("home.html")
    # time1=random.randint(1,10)
    # print(time1)
    # return render_template("home.html",time=time1)

def is_admin(f):
    """用来判断用户是否登录成功"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 判断session对象中是否有seesion['user']等于root,
        # 如果包含信息， 则登录成功， 可以访问主页；
        # 如果不包含信息， 则未登录成功， 跳转到登录界面;；
        if session.get('user', None) == 'root':
            return f(*args, **kwargs)
        else:
            flash('只有管理员root才能访问%s' % f.__name__)
            return redirect(url_for('login'))

    return wrapper

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', None)
        password = request.form.get('password', None)
        # 当所有的信息遍历结束， 都没有发现注册的用户存在， 则将注册的用户添加到服务器， 并跳转登录界面;
        for user in users:
            if user['username'] == username:
                return render_template('register.html', messages='用户%s已经存在' % username)
        else:
            users.append(dict(username=username, password=password))
            # 出现一个闪现信息;
            flash('用户%s已经注册成功，请登陆.....' % username, category='info')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', None)
        password = request.form.get('password', None)
        for user in users:
            if user['username'] == username and user['password'] == password:
                #  将用户登录的信息存储到session中;
                session['user'] = username
                return redirect(url_for('setting'))
            if user['username'] == username and user['password'] != password:
                # 出现一个闪现信息;
                flash("密码错误，请重新登陆","wrong")
                return redirect("#idlogin")
                # return redirect(request.url)
        else:
            # flash(ss,"ss")
            flash("该用户不存在，请重新登陆","none")
            return redirect("#idlogin")
    return render_template("home.html")

@app.route('/list')
@is_login
def list():
    return render_template('list.html', users=users)

@app.route('/logout')
def logout():
    #  将用户存储到session中的信息删除;
    session.pop('user')
    flash('注销成功....')
    return render_template('home.html')

@app.route('/delete/<string:username>/')
def delete(username):
    for user in users:
        # 用户存在， 则删除;
        if username == user['username']:
            users.remove(user)
            flash('删除%s用户成功' % username)
    # else:
    #     flash('用户%s不存在'%username)

    # 删除成功， 跳转到/list/路由中.....
    return redirect(url_for('list'))

@app.route("/setting")
@is_login
def setting():
    return render_template("setting.html")

###################### 西门子 #######################################

@app.route("/siemens",methods=("GET","POST"))
@is_login
def siemens():
    ## 反馈系统运行状态
    def s7connect(ip, rack, slot):
        try:
            plc = client.Client()
            # print(ip,rack,slot)
            plc.connect(ip, rack, slot)
        except Exception as e:
            flash("连接失败，请确认IP或网络连通性", "connect0")
        else:
            state = plc.get_cpu_state()
            flash(ip + " 连接成功", "connect1")
            return plc

    if request.method =="POST":
        # flash("run", "run")
        # print("222222222")
        forminfo = request.form.to_dict()
        # print(forminfo)

        # 该页面的表单信息，只要submit都传到这里，其中包括plc的连接信息 ip[str] rack[int] slot[int]
        # 还包括变量地址信息以及influxdb配置信息，通过字典长度区分各个表单
        global plc
        if (forminfo)=={}: #上传变量表
            try:
                f = request.files.get('file') ## 获取文件
                print(f.filename)
                f.save('D:/' + secure_filename(f.filename))  ## C盘写入权限受限Permission denied
            except Exception as e:
                print(e)
                flash(e,"uploadstatus")
            else:
                ## 保存测试
                flash("变量表上传成功", "uploadstatus")
                # try:
                #     f.save('D:/' + secure_filename(f.filename))  ## C盘写入权限受限Permission denied
                # except Exception as e:
                #     print(e)
                #     flash(e, "uploadstatus")
                # else:
                #     flash("变量表上传成功","uploadstatus")

        if len(forminfo)==3: #PLC 连接信息
            print(forminfo)
            plc=s7connect(str(forminfo["ipaddress"]),int(forminfo["rack"]),int(forminfo["slot"])) #数据类型转换
            # ip=forminfo["ipaddress"]
        if len(forminfo)==2: #变量地址
            print(forminfo)
            data=s7read(plc,forminfo["iqm"],forminfo["address"])
            print(data)
                # return data

        elif len(forminfo)==4: # influxdb连接信息
            print(forminfo)
            influxdbip = forminfo["influxdb"]
            token = forminfo["token"]
            measurement = forminfo["measurement"]
            cycle=forminfo["cycle"]
            influxDB(influxdbip,token,measurement,cycle)
        # flash(forminfo,"connect1")
        return redirect("#")
        # return render_template("siemens.html")
    return render_template("siemens.html")


@app.route("/siemensdisconnect",methods=("POST","GET"))
@is_login
def s7disconnect():
    try:
        print("disconnect")
        # plc = client.Client()
        plc.disconnect()
    except Exception:
        flash("断开失败","connect0") ##connect0 失败提醒
    else:
        flash("已断开连接","connect1") ## connect1 操作成功提示
    return redirect("/siemens#connection")

@app.route("/s7read",methods=("POST","GET"))
@is_login
def s7read(plc,iqm,address):

    ss=""  # 标识I/Q/M
    t=areas[iqm]
    # print(address)
    if address=='':
        address2=0.0
    else:
        address2=(float(address))
    if t ==129:
        ss = "I "
    if t == 130:
        ss = "Q "
    if t == 131:
        ss = "M "

    b = (int(address2))
    c = (int((address2-b)*10))

    print(t,b,c)
    try:
        variable = ss + address
        print(variable)
        timenow = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        result=plc.read_area(t,0,b,8)  ## 变量类型，0，地址起始，固定8位
        data = get_bool(result, 0, c)  ## 地址偏移值
        ttt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    except Exception as e:
        print(e)
    else:
        # flash(data, "value")
        # flash(timenow, "time")
        # flash(variable,"variable")
        siemensdata = dict(zip(variable, data))
        print(siemensdata)
    return render_template("rockwell.html", siemensdata=siemensdata, ttt=ttt)

    # except Exception as e:
    #     print(e)
    #     flash(e,"connect1")
    # else:
    #     pass
    #     redirect("#iqmselect")

########################### 倍福 ################################
@app.route("/beckoff",methods=["POST","GET"])
@is_login
def beckoff():
    # return render_template("b.html")
    # if request.method=='POST':
    #     aa=request.files.get("ss")
    return render_template("beckoff.html")

######################### 罗克韦尔 ##############################

global rockwellip,rockwell_device_list,taglist
rockwellip=''
rockwelldata=()
ttt=''

@app.route("/rockwell",methods=["POST","GET"])
@is_login
def rockwell():
    ## Rockwell AB PLC # #108厂房设备
    return render_template("rockwell.html")

@app.route("/rockwellread")
@is_login
def rockwellread():    #'读取函数'
    print("readlist")
    print(taglist)

    ### 分批读取函数 每次读取10个变量
    def readten(tags_list):
        l = len(tags_list)  # 变量表长度，如果大于10 必须分批读取保证不报错
        x = l // 10  # 取整
        y = l % 10  # 取余数
        a = 0  # 每一组变量的上标
        val = []  # 初始化列表 每一组变量值
        for n in range(x):
            if n < x:
                val = val + comm.Read(tags_list[10 * a:10 * (a + 1)])
                a += 1
                n += 1
            if n == x and y != 0:
                val = val + comm.Read(tags_list[10 * a:10 * a + y])
        vall = val
        return vall

    with PLC() as comm:
        tagname=[]
        tagvalue=[]
        comm.IPAddress=rockwellip
        aa=readten(taglist) #调用函数分批读取变量
        ttt=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(aa)
        for a in aa:
            tagname.append(a.TagName)
            tagvalue.append(a.Value)
        # 输出到前端页面
        rockwelldata=dict(zip(tagname,tagvalue))
        print(rockwelldata)
        # return redirect("#data")
    return render_template("rockwell.html",rockwelldata=rockwelldata,ttt=ttt)
    # return render_template("rockwell.html")

def rockwellreadexcel(file):
    print("readexcel"+file.filename)
    # data = pd.DataFrame(pd.read_excel(file))
    # data2 = pd.read_excel(file, usecols=[0], header=None)  ##第一列 无表头 输出为DataFrame格式 带索引
    data2 = pd.read_excel(file)  ##输出为DataFrame格式 后续剔除未知类型
    # data2=data2.dropna() ##剔除异常的nan
    data2 = data2[data2['TagType'].isin(["BOOL"])] ##可以读取的类型 ["BOOL", "TIMER", "REAL"]
    ##剔除程序名和已知类型之外的数据
    data2 = data2['TagName']
    print(data2)
    global taglist
    taglist = data2.to_numpy().tolist()  # 转数组 转列表
    # taglist = sum(data2, [])  # 嵌套列表平铺 变量表list
    print(taglist)

@app.route("/rockwellscan",methods=["POST","GET"])
@is_login
def rockwellscan():
    with PLC() as comm:
        # 设备扫描
        deviceip = []
        devicename = []
        devices = comm.Discover()
        for device in devices.Value:
            deviceip.append(device.IPAddress)
            devicename.append(device.ProductName + ' ' + device.IPAddress)
        global rockwell_device_list
        rockwell_device_list = dict(zip(devicename, deviceip))  # 创建设备字典 写入全局变量
        scanresult="扫描到"+str(len(rockwell_device_list))+"台设备"
        print(scanresult)
        flash(scanresult,"scanresult") #扫描完成flash提示
        return redirect(url_for('rockwellscan2'))
        # dev_list=str(device_dict)
        # return redirect(url_for(rockwell)) # url_for函数跳转
        # flash(device_dict,"device_dict") #设备扫描结果显示到前端页面下拉列表

@app.route("/rockwellscan2",methods=["POST","GET"])
@is_login
def rockwellscan2():
        if request.method == "POST":
            flash("run", "run")
            forminfo=request.form.to_dict() ## to_dict()加括号
            # 该页面的表单信息，只要submit都传到这里
            # forminfo=request.form.get('devicelist') # 获取到的value是str字符串
            # 还包括变量地址信息以及influxdb配置信息，通过字典长度区分各个表单
            print(forminfo)
            # print(type(forminfo))
            # aa=type(forminfo)

            ######## 每次“开始连接”实际只是获取选择的设备ip并写入全局变量
            # 程序逻辑调整为rockwellscan运行后跳转rockwellscan2 但是页面会整体刷新造成列表变化~~~~~~~~~~~
            if len(forminfo)==1 : # AB PLC 连接信息 只需要IP
                print(forminfo)
                aa=(forminfo["devicelist"]).split(" ")
                aa=aa[len(aa)-1] #获取ip
                global rockwellip # 全局变量 要先声明globa 再修改
                rockwellip=aa
                ss=("已连接到 "+str(forminfo["devicelist"]))
                flash(ss, "scanresult")  # 连接完成
                # print(rockwellip)

            # if (forminfo)=={}:  # 上传变量表 #
            if len(forminfo)==2: #### 是excel就调用readexcel
                print("22222222222")
                try:
                    file = request.files.get('file')
                    file.save('D:/' + secure_filename(file.filename))  ## C盘写入权限受限Permission denied 暂存在D盘，linux中应该没问题
                    rockwellreadexcel(file)
                except Exception as e:
                    print(e)
                    flash(e, "uploadstatus")
                else:
                    # 保存测试
                    flash("变量表上传成功", "uploadstatus")

            # if len(forminfo) == 2:  # 变量地址
            #     print(forminfo)
            #     data = s7read(plc, forminfo["iqm"], forminfo["address"])
            #     print(data)
            #     # return data

            elif len(forminfo) == 4:  # influxdb连接信息
                # print("11111111111")
                print(forminfo)
                influxdbip = forminfo["influxdb"]
                token = forminfo["token"]
                measurement = forminfo["measurement"]
                cycle = forminfo["cycle"]
                influxDB(influxdbip, token, measurement, cycle)
            # flash(forminfo,"connect1")
        # return redirect("#")
        # flash(rockwell_device_list,"dev_list") # flash只能传递字符串
        # return jsonify()
        # return redirect(url_for("rockwell"))
        return render_template("rockwell.html",dev_list=rockwell_device_list)#设备扫描结果显示到前端页面下拉列表
    ## 定向页面逻辑，此处要在rockwellscan中处理POST请求
    ## 前端调用后台程序 href=“xx” 通过路由调用，还有没有别的方法 采用url_for()跳转 参考登录函数处理方法
    # return redirect("#")

@app.route("/rockwell_get_all_vars")
@is_login
#### 获取所有变量 并下载 # 待办，剔除程序名称，编写变量读取函数，连续获取变量表 时间不变bug
def rockwell_get_all_vars(): #
    # print("111111111111111")
    with PLC() as comm:
        # print("111111111111")
        ####### 无法连续运行重复获取变量表？ 连续点击不进入循环 直接下载附件？？ 如果要刷新变量表需要再次“开始连接”##############
        print(rockwellip)
        if rockwellip=='':
            print("请先选择设备IP地址")
        else:
            print(rockwellip)
            comm.IPAddress = rockwellip #全局变量
            # comm.IPAddress="192.168.100.200"
            print("2222222222")
            try:
                tags = comm.GetTagList() #输出是Response结构体类型需要解析
                comm.Close()
            except Exception as e:
                print(e)
                #缺一个return ，读取错误的错误处理
            else:
                tagname=[]
                tagtype=[]
                head=["TagName","TagType"]
                for t in tags.Value:
                    tagname.append(t.TagName)
                    tagtype.append(t.DataType)
                taglist = pd.DataFrame({'tagname': tagname, 'tagtype': tagtype}) #采用Pandas格式化
                # print(taglist)
                tt = datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S') #时间标识符
                filepath=("D:/Taglist "+tt+".xlsx")
                print(filepath)
                ## 变量表文件暂存以备发送和自动读取
                taglist.to_excel(filepath, encoding='utf-8', index=False, header=head) #写入excel
                ## 变量表文件下载
                return send_file(filepath,as_attachment=True) #向前端发送文件 下载 比send_from_directory简化
                # return send_from_directory(filepath,as_attachment=True) #

######################## OPC UA Client 用于写入InfluxDB ####################################
@app.route("/opcua")
@is_login
def opcua():
    # return render_template("b.html")
    return render_template("opcua.html")

######################## OPC UA Server 用于转换为OPC UA格式数据
# basic server仅支持UA expert Prosys还不支持 ########################
@app.route("/opcuaserver")
@is_login
def opcuaserver():
    # return render_template("b.html")
    return render_template("opcua.html")

########################################## 多线程测试
import threading
global www
www=1
@app.route("/test1",methods=["GET"])
# @is_login
def aaa():
    print("main thread")
    t1 = threading.Thread(target=DownThread,args=())
    t1.setDaemon(True)
    t1.start()
    if request.method is "GET":
        DownThread.terminate()
        print("End")
    # else:
    #     print("Run")
    #     while 1:
    #         pass
    return redirect("/")

# @app.route("/test2")
# def nnn():
#     return redirect(url_for(ww()))
# @app.route("/kkkkkkkkkk")
# def ww():
#     global www
#     www=0
#     return render_template("home.html")

# @is_login
def fun():
    i=0
    while 1:
        i=i+1
        print(i)
        time.sleep(1)


class DownThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, n):
        i = 0
        while 1:
            i = i + 1
            print(i)
            time.sleep(1)


######################## InfluxDB 共用函数 #############################
@app.route("/influxDB",methods=("POST","GET"))
@is_login
def influxDB(influxdbip,token,measurement,cycle):
    print("influxDB写入")
    a=1
    bucket = "test"
    token="HTvG6oIApfABybjjYd_6Jehf8AEWkLStYw0qftanx9ijF05-UsLZ9pVqI604PwuRlhv8IkuIZshYaqVFTC0DXA=="
    client = InfluxDBClient(url=influxdbip,token=token,org="su")
    write_api = client.write_api(write_options=SYNCHRONOUS)
    # query_api = client.query_api()
    cycle=(int(cycle)/1000) #单位ms
    # cycle=(cycle)
    flash("开始写入influxDB","influx")
    while 1:
        try:
            ss=1
            xx=2
            p = Point(measurement).tag("location", "108厂房").field("温度", ss)
            q = Point(measurement).tag("location", "beijing").field("2", xx)
            write_api.write(bucket=bucket, org="su", record=[p,q])
            # print("2222")
            time.sleep(cycle)
        except a==0:
            pass # Stop writing

        except Exception as e:
            print(e)
            break

################### app 主程序 （测试用） 部署版本采用nginx托管 ##########################
app.run(host="0.0.0.0",port=5000)