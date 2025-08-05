import os
import subprocess
import time
import threading
import signal
import queue
import shutil
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException
import random
import re
import multiprocessing
from selenium.common.exceptions import NoAlertPresentException


def extract_bundle_id(filename):
    # 去掉文件扩展名 ".ipa"
    filename = filename[:-4]
    # 从后向前找到第三个 "-"，并提取该位置之前的所有内容作为 bundleId
    parts = filename.rsplit('-', 3)
    if len(parts) == 4:
        bundle_id = parts[0]
        return bundle_id
    return None

def run_frida_command(frida_cmd, output_queue, process):
    try:
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if "Documents Path:" in output:
                # 将冒号后的内容赋值给 documentspath
                documents_path = output.split("Documents Path: ")[1].strip()
                output_queue.put(documents_path)
                return  # 找到所需信息后退出函数
    except Exception as e:
        output_queue.put(e)

def run_command_with_timeout(frida_cmd, timeout):
    output_queue = queue.Queue()
    process = subprocess.Popen(frida_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    frida_thread = threading.Thread(target=run_frida_command, args=(frida_cmd, output_queue, process))

    frida_thread.start()

    time.sleep(timeout)
    if frida_thread.is_alive():
        print("Timeout reached, killing the process.")
        process.terminate()  # 终止进程
        frida_thread.join()  # 确保线程安全结束

    # 从队列中获取结果
    try:
        documentspath = output_queue.get_nowait()
        if isinstance(documentspath, Exception):
            raise documentspath
        # print(f"Documents Path: {documentspath}")
        return documentspath
    except queue.Empty:
        print("No 'Documents Path' found within the timeout period.")
        return None



def run_objection(UDID,BundleId):
    # 启动 objection explore 命令
    process = subprocess.Popen(
        ['objection','-S', UDID, '-g', BundleId, 'explore'],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True
    )

    # 等待 objection REPL 启动完成
    time.sleep(5)  # 调整等待时间以确保 REPL 启动完成

    # 向 objection REPL 发送命令
    process.stdin.write('ios sslpinning disable\n')
    process.stdin.flush()

    # 等待命令执行完成
    time.sleep(5)  # 调整等待时间以确保命令完成执行
    process.stdin.close()
    return process


def take_screenshots(capabilities,appiumurl,out_dir,duration):
    appium_options = AppiumOptions()
    appium_options.load_capabilities(capabilities)
    # 初始化Appium驱动
    driver = webdriver.Remote(appiumurl, options=appium_options)

    # 确保保存截图的目录存在
    os.makedirs(out_dir, exist_ok=True)

    start_time = time.time()
    end_time = start_time + duration

    try:
        while time.time() < end_time:
            timestamp = int(time.time())  # 使用当前时间戳作为文件名
            screenshot_file = os.path.join(out_dir, f'screenshot_{timestamp}.png')

            # 截取屏幕截图
            driver.get_screenshot_as_file(screenshot_file)
            # print(f"Screenshot saved as {screenshot_file}")
            # 等待2秒
            time.sleep(5)
        driver.quit()
    except Exception as e:
        print(f"an error occureed during screenshot: {e}")



def checkudid(udid):
    try:
        result = subprocess.run(['idevice_id', '-l'], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        # 检查输出中是否包含预定义的UDID
        if udid in output:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing the command: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False


def check_jailbreak(ip):
    print(ip)
    try:
        result = subprocess.run(
            ['sshpass', '-p', "alpine", 'ssh', f'root@{ip}', 'exit'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
        )
        print("check jailbreak")
        if "Connection refused" in result.stderr.decode() or "Connection refused" in result.stdout.decode():
            print(f"Connection refused to {ip}. The iPhone is likely not jailbroken.")
            return False
        else:
            print("already jailbreak")
            return True
    except subprocess.TimeoutExpired:
        # 超时错误处理
        print(f"Connection to {ip} timed out.")
        return False
    except Exception as e:
        # 处理其他潜在的异常
        print(f"An error occurred: {e}")
        return False
    
def extract_logfile(documentspath,ip):
    print(documentspath)
    if documentspath is None:
        return None
    logfile = os.path.join(documentspath, "logInfo.txt")
    coordinates = []
    try:
        result = subprocess.run(
            ['sshpass', '-p', "alpine", 'ssh', f'root@{ip}', f'cat {logfile}'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2
        )
        log_content = result.stdout.decode()
        lines = log_content.splitlines()
        lines = [line for line in lines if line.strip()]
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                first_line = lines[i].strip()
                second_line = lines[i + 1].strip()
                timestamp_match = re.search(r'screenshot saved as: (screenshot_\d{8}_\d{6}\.png)', second_line)
                if timestamp_match:
                    timestamp = timestamp_match.group(1)

                # 检查第一行是否包含 'adClass point'
                if 'adClass point' in first_line:
                    # 提取坐标
                    pattern = r'\{(\d+(\.\d+)?),\s*(\d+(\.\d+)?)\}'
                    matches = re.findall(pattern, first_line)
                    if len(matches) >= 2:
                        x = float(matches[0])  
                        y = float(matches[1])  
                        coordinates.append((timestamp,x, y))
        return coordinates
    except subprocess.TimeoutExpired:
        # 超时错误处理
        print(f"Connection to {ip} timed out.")
        return False
    except Exception as e:
        # 处理其他潜在的异常
        print(f"An error occurred: {e}")
        return False

def click_login(driver):
    flag = True
    while flag is True:
        time.sleep(1)
        try:
            # button = driver.find_element(AppiumBy.ACCESSIBILITY_ID, '以后')
            button = driver.find_element(AppiumBy.ACCESSIBILITY_ID, 'Not Now')
            button.click()
        except NoSuchElementException:
            print("No such element")
            flag = False

def jailbreak(udid,capabilities,appiumurl):
    try:
        appium_options = AppiumOptions()
        appium_options.load_capabilities(capabilities)
        driver = webdriver.Remote(appiumurl, options=appium_options)
        print("appium connect")
        time.sleep(5)
        click_login(driver)
        button = driver.find_element(AppiumBy.ACCESSIBILITY_ID, 'Jailbreak')
        button.click()
        time.sleep(40)
        # 点击左上角的X
        click_login(driver)
        driver.tap([(20,58)])
        print("tap x")
        time.sleep(1)
        click_login(driver)
        button = driver.find_element(AppiumBy.ACCESSIBILITY_ID, 'OK')
        button.click()

    except Exception as e:
        print("jailbreak failed")
        print(e)
        
def find_and_click_agree(driver,clicked_elements):
    try:
        # 查找所有包含 "同意" 字样且不包含 "不同意" 字样的元素
        # agree_elements = driver.find_elements(
        #     AppiumBy.XPATH,
        #     "//*[(contains(@text, '同意') or contains(@text, '继续') or contains(@text, '取消') or contains(@text, '以后') or contains(@text, '允许') or contains(@text, '确定') or contains(@text, '好') or contains(@text, '无线局域网与蜂窝网络')) and not(contains(@text, '不'))]"
        #     " | //*[(contains(@name, '同意')  or contains(@name, '继续') or contains(@name, '取消') or contains(@name, '以后') or contains(@name, '允许') or contains(@name, '确定') or contains(@name, '好') or contains(@name, '无线局域网与蜂窝网络')) and not(contains(@name, '不'))]"
        #     " | //*[(contains(@label, '同意') or contains(@label, '继续') or contains(@label, '取消') or contains(@label, '以后') or contains(@label, '允许') or contains(@label, '确定') or contains(@label, '好') or contains(@label, '无线局域网与蜂窝网络')) and not(contains(@label, '不'))]"
        # )
        agree_elements = driver.find_elements(
            AppiumBy.XPATH,
            "//*[(contains(@text, 'agree') or contains(@text, 'Not Now') or contains(@text, 'Cancel') or contains(@text, 'Agree') or contains(@text, 'Yes') or contains(@text, 'Allow') or contains(@text, 'Continue') or contains(@text, 'OK') or contains(@text, 'WLAN & Cellular')) and not(contains(@text, 'NO') or contains(@text, 'Don'))]"
            " | //*[(contains(@name, 'agree')  or contains(@name, 'Not Now')  or contains(@name, 'Cancel') or contains(@name, 'Agree') or contains(@name, 'Yes') or contains(@name, 'Allow') or contains(@name, 'Continue') or contains(@name, 'OK') or contains(@name, 'WLAN & Cellular')) and not(contains(@name, 'NO') or contains(@name, 'Don'))]"
            " | //*[(contains(@label, 'agree') or contains(@label, 'Not Now') or contains(@label, 'Cancel') or contains(@label, 'Agree') or contains(@label, 'Yes') or contains(@label, 'Allow') or contains(@label, 'Continue') or contains(@label, 'OK') or contains(@label, 'WLAN & Cellular')) and not(contains(@label, 'NO') or contains(@label, 'Don'))]"
        )

        for element in agree_elements:
            # 确保该元素未被点击过
            if element not in clicked_elements:
                element.click()  # 点击该元素
                clicked_elements.append(element)  # 记录已经点击的元素
                return True  # 成功点击后退出
    except NoSuchElementException:
        print("未找到符合条件的按钮")
        return False  # 未找到可点击的同意元素
    
def wda_click(capabilities,appiumurl,documentspath,deviceip,bundleId,out_dir):
    try:
        appium_options = AppiumOptions()
        appium_options.load_capabilities(capabilities)
        driver = webdriver.Remote(appiumurl, options=appium_options)

        end_time = time.time() + 125
        clicked_elements = []
        timestamps = []

        try:
            while time.time() < end_time:
                # 保持应用在前台
                driver.activate_app(bundleId)
                while find_and_click_agree(driver,clicked_elements):
                    time.sleep(1)
                # 点击广告
                logresult = extract_logfile(documentspath,deviceip)
                tapflag = False
                for timestamp, x, y in logresult:
                    if timestamp not in timestamps:
                        tapflag = True
                        timestamps.append(timestamp)
                        driver.tap([(x, y)])
                        time.sleep(1)
                if not tapflag:
                    # 随机点击
                    width = driver.get_window_size()['width']
                    height = driver.get_window_size()['height']
                    x = random.randint(0, width)
                    y = random.randint(0, height)
                    driver.tap([(x, y)])
                timestamp = int(time.time())  # 使用当前时间戳作为文件名
                screenshot_file = os.path.join(out_dir, f'screenshot_{timestamp}.png')

                # 截取屏幕截图
                driver.get_screenshot_as_file(screenshot_file)
                time.sleep(3)
        except Exception as e:
            print(e)
        driver.quit()

    except Exception as e:
        print("appium failed : {e}")
        
def run_wda(wdacommand,wda_process,working_directory):
    try:
        while True:
            retcode = wda_process.poll()
            if retcode is not None:
                print(f"WDA process exited with code {retcode}, restarting...")
                wda_process = subprocess.Popen(wdacommand, cwd=working_directory)
            else:
                # WDA 正常运行
                time.sleep(60)  # 每隔 5 秒检查一次
    except Exception as e:
        print(f"An error occurred: {e}")
        if wda_process:
            wda_process.terminate()  
        

def process_device(deviceip, directory, output_dir, id, UDID):
    ipafiles = os.listdir(directory)
    mitmproxydir = "/Users/tmliu/Documents/XCodeProject/MitmProxy/log"
    if id == 1:
        ipafiles = list(reversed(ipafiles))
    if id == 2:
        random.shuffle(ipafiles)
    wdacommand = ["xcodebuild", "-project", "WebDriverAgent.xcodeproj", "-scheme", "WebDriverAgentRunner",
           "-destination", f"id={UDID}", "test"]
    working_directory = "/Users/tmliu/Documents/appium-webdriveragent"
    if id == 0:
        working_directory = "/Users/tmliu/Documents/appium-webdriveragent"
    elif id == 1:
        working_directory = "/Users/tmliu/Documents/appium-webdriveragent2"
    elif id == 2:
        working_directory = "/Users/tmliu/Documents/appium-webdriveragent3"
    iosversion = ""
    appiumurl = ""
    wdalocalport = 0
    if id == 0:
        mitmproxydir = os.path.join(mitmproxydir, "device1")
        iosversion = "14.2"
        appiumurl = "http://localhost:4723"
        wdalocalport = 8100
    elif id == 1:
        mitmproxydir = os.path.join(mitmproxydir, "device2")
        iosversion = "14.0"
        appiumurl = "http://localhost:4724"
        wdalocalport = 8101
    elif id == 2:
        mitmproxydir = os.path.join(mitmproxydir, "device3")
        iosversion = "14.0"
        appiumurl = "http://localhost:4725"
        wdalocalport = 8102
    wdaprocess = subprocess.Popen(wdacommand, cwd=working_directory)
    wda_thread = threading.Thread(target=run_wda,args=(wdacommand,wdaprocess,working_directory,))
    wda_thread.start()
    time.sleep(15)
    for ipafile in ipafiles:
        bundleId = extract_bundle_id(ipafile)
        print(ipafile)
        
        while not checkudid(UDID):
            print(f"idevice_id -l not found device {UDID}")
            time.sleep(30)
        
        if not ipafile.endswith("ipa"):
            continue     

        jailbreakcapabilities = {
            "platformName": "iOS",
            "appium:platformVersion": iosversion,
            "appium:deviceName": "iPhone",
            "appium:udid": UDID,
            "appium:bundleId": "com.ichitaso.undecimus",
            "appium:automationName": "XCUITest",
            "wdaLocalPort": wdalocalport,
            "wdaRemotePort": wdalocalport
        }
       

        capabilities = {
            "platformName": "iOS",
            "appium:platformVersion": iosversion,
            "appium:deviceName": "iPhone",
            "appium:udid": UDID,
            "appium:bundleId": bundleId,
            "appium:automationName": "XCUITest",
            "wdaLocalPort": wdalocalport,
            "wdaRemotePort": wdalocalport
        }
        # 检查是否越狱状态
        
        ipafilePath = os.path.join(directory, ipafile)
        if os.path.exists(outputpath):
            continue
        outputpath = os.path.join(output_dir, f"{bundleId}_dir")
        os.makedirs(outputpath, exist_ok=True)
        screenshotpath = os.path.join(outputpath, "recordScreentshots")
        os.makedirs(screenshotpath, exist_ok=True)
        shutil.rmtree(mitmproxydir)
        os.makedirs(mitmproxydir, exist_ok=True)

        while not check_jailbreak(deviceip):
            try:
                print("not jailbreak")
                time.sleep(30)

                if wdaprocess.poll() is not None:
                    print("进程已结束，重新启动...")
                    wdaprocess = subprocess.Popen(wdacommand, cwd=working_directory)  # 重新启动进程
                    time.sleep(15)
                print("begin jail break")
                jailbreak(UDID,jailbreakcapabilities,appiumurl)
                time.sleep(30)
            except Exception as e:
                print("jailedbreak failed")
        
        if not os.path.exists(ipafilePath):
            print("not exist")
            continue
        installcmd = f"ideviceinstaller -u {UDID} -i \"{ipafilePath}\""

        Installflag = False
        try:
            result = subprocess.run(installcmd, shell=True, check=True, capture_output=True, text=True,
                                    encoding='utf-8', timeout=120)
            print("Command Output:", result.stdout)
            if "Install: Complete" in result.stdout:
                Installflag = True
        except subprocess.CalledProcessError as e:
            print(f"错误代码: {e.returncode}")
            print(f"标准输出: {e.stdout}")
            print(f"标准错误: {e.stderr}")
        except subprocess.TimeoutExpired as e:
            print(f"命令超时: {e.cmd}")

        os.rename(ipafilePath, ipafilePath + "_done")
        if not Installflag:
            print(f"安装失败: {bundleId}")
            continue
        
        time.sleep(5)

        objectionprocess = run_objection(UDID,"com.apple.AppStore")
        

        if wdaprocess.poll() is not None:
            print("进程已结束，重新启动...")
            wdaprocess = subprocess.Popen(wdacommand, cwd=working_directory)  # 重新启动进程
            time.sleep(15)
            
        documentspath = ""
        document_frida_cmd = f"frida -D {UDID} -f {bundleId} -l /Users/tmliu/Documents/XCodeProject/Frida/code/getuuid.js"
        documentcount = 0
        while documentspath == "":
            documentcount += 1
            if documentcount > 3:
                break
            try:
                documentspath = run_command_with_timeout(document_frida_cmd, timeout=10)
            except:
                print("execute ipa failed")
        if documentcount > 3:
            print("get documents path failed")
            continue 

        # capabilities2 = {
        #     "platformName": "iOS",
        #     "appium:platformVersion": iosversion,
        #     "appium:deviceName": "iPhone",
        #     "appium:udid": UDID,
        #     "appium:automationName": "XCUITest",
        #     "wdaLocalPort": wdalocalport,
        #     "wdaRemotePort": wdalocalport
        # }
        # screenshot_thread = threading.Thread(target=take_screenshots, args=(capabilities2,appiumurl,screenshotpath, 120))

        # # 启动线程
        # screenshot_thread.start()
        
        # try:
        #     objectionthread = threading.Thread(target=run_objection, args=(UDID,bundleId,))
        #     objectionthread.start()
        # except:
        #     print("objection failed")
        time.sleep(5)
        try:
            wdaclickprocess = multiprocessing.Process(target=wda_click, args=(capabilities,appiumurl,documentspath,deviceip,bundleId,screenshotpath,))
            wdaclickprocess.start()
        except:
            print("objection failed")
        frida_cmd = f"frida -D {UDID} -f {bundleId} -l /Users/tmliu/Documents/XCodeProject/Frida/code/test.js"
        try:
            run_command_with_timeout(frida_cmd, timeout=130)
        except:
            print("execute ipa failed")
        # screenshot_thread.join()
        wdaclickprocess.terminate()  # 强制终止子进程
        wdaclickprocess.join()
        # print(documentspath)
        # obpid = objectionthread.native_id  # 在某些 Python 版本中，可能需使用 `thread.ident` 替代
        # try:
        #     # 终止子进程
        #     subprocess.run(['kill', '-9', str(obpid)], check=True)
        #     print(f"Terminated process with PID: {obpid}")
        # except Exception as e:
        #     print(f"Failed to terminate process: {e}")


        mitmoutputpath = os.path.join(outputpath,"log")
        os.makedirs(mitmoutputpath, exist_ok=True)
        shutil.copytree(mitmproxydir, mitmoutputpath, dirs_exist_ok=True)
        print("begin transit")
        # print("documentpaths: "+ documentspath)
        # SCP commands for copying plist, txt, and ScreenShots
        scp_cmds = [
            f"sshpass -p 'alpine' scp root@{deviceip}:{documentspath}/*.plist {outputpath}",
            f"sshpass -p 'alpine' scp root@{deviceip}:{documentspath}/*.txt {outputpath}",
            f"sshpass -p 'alpine' scp -r root@{deviceip}:{documentspath}/ScreenShots {outputpath}"
        ]

        for scp_cmd in scp_cmds:
            try:
                result = subprocess.run(scp_cmd, shell=True, check=True, capture_output=True, text=True,
                                        encoding='utf-8', timeout=60)
                print("Command Output:", result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"错误代码: {e.returncode}")
                print(f"标准输出: {e.stdout}")
                print(f"标准错误: {e.stderr}")
            except subprocess.TimeoutExpired as e:
                print(f"命令超时: {e.cmd}")

        print("传输完成，开始卸载")
        uninstallcmd = f"ideviceinstaller -u {UDID} -U {bundleId}"
        try:
            result = subprocess.run(uninstallcmd, shell=True, check=True, capture_output=True, text=True,
                                    encoding='utf-8', timeout=60)
            print("Command Output:", result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"错误代码: {e.returncode}")
            print(f"标准输出: {e.stdout}")
            print(f"标准错误: {e.stderr}")
        except subprocess.TimeoutExpired as e:
            print(f"命令超时: {e.cmd}")

        try:
            objectionprocess.terminate()
        except Exception as e:
            print(f"终止进程时发生错误：{e}")

        print("休息20s")
        time.sleep(20)

if __name__ == "__main__":
    directory = "/Volumes/Backup Plus/app/US"
    output_dir = "/Users/tmliu/Documents/XCodeProject/iosAdTestRecord/CN"

    # device_ips = ["172.19.193.233", "172.19.194.107"]
    # UDIDs = ["cef2b64e9d946d25951abad69c06d5f16d902118","809d6a387545a030d2993ce71e0c86e9fe5a11cd"]

    device_ips = ["172.19.193.233", "172.19.194.107", "172.19.193.18"]
    UDIDs = ["cef2b64e9d946d25951abad69c06d5f16d902118","809d6a387545a030d2993ce71e0c86e9fe5a11cd","ed50edc6c6d355ebc62ab98446ac4e7eb1aeb1fd"]
    # device_ips = ["172.19.192.233"]
    # UDIDs = ["cef2b64e9d946d25951abad69c06d5f16d902118"]
    threads = []
    for i, deviceip in enumerate(device_ips):
        t = threading.Thread(target=process_device, args=(deviceip, directory, output_dir, i, UDIDs[i]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()