import subprocess
import threading
import time
import os
import random
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException
import multiprocessing


def dynamic_process(app_id, UDID, bundle_id, country, out_dir="out"):
    """
    动态处理函数，执行安装和自动化测试。
    :param app_id: 应用 ID
    :param UDID: 设备唯一标识符
    """
    # 需要修改，时刻监控webdriver有没有挂掉（极有可能中途挂掉）
    # 结束后需要 杀死
    # 安装逻辑
    ipafilePath = f"ipa/{app_id}.ipa"
    installcmd = f"ideviceinstaller -u {UDID} -i \"{ipafilePath}\""
    subprocess.run(installcmd, shell=True, check=True)
    out_dir = os.path.join(out_dir, app_id)
    wdaport = 0
    appiumurl=""
    if(country=="cn"):
        wdaport = 8100
        appiumurl = "http://localhost:4723"
    elif(country=="us"):
        wdaport = 8101
        appiumurl = "http://localhost:4724"

    # working_directory = "/Users/tmliu/Documents//Users/tmliu/Documents/appanalyzer-ios/WebDriverAgent"

    # 启动 WebDriverAgent 服务
    # wdacommand = [
    #     "xcodebuild", "-project", "WebDriverAgent.xcodeproj", "-scheme", "WebDriverAgentRunner",
    #     "-destination", f"id={UDID}", "test"
    # ]
    # wda_process = subprocess.Popen(wdacommand, cwd=working_directory)
    # wda_thread = threading.Thread(target=run_wda, args=(wdacommand, wda_process, working_directory))
    # wda_thread.start()
    
    # time.sleep(10)  # 等待 WDA 启动
    
    # # 等待 WDA 进程正常启动
    # print("Waiting for WDA process to start...")
    # max_wait_time = 60  # 最大等待时间60秒
    # wait_start = time.time()
    # while time.time() - wait_start < max_wait_time:
    #     if wda_process.poll() is None:  # 进程仍在运行
    #         print("WDA process is running normally")
    #         break
    #     time.sleep(20)
    # else:
    #     raise Exception("WDA process failed to start within the expected time")
    
    # 启动appium服务并随机点击
    capabilities = {
        "platformName": "iOS",
        "appium:platformVersion": "16.2",
        "appium:deviceName": "iPhone",
        "appium:udid": UDID,
        "appium:bundleId": bundle_id,
        "appium:automationName": "XCUITest",
        "wdaLocalPort": wdaport,
        "wdaRemotePort": wdaport
    }
    
    try:
        wdaclickprocess = multiprocessing.Process(target=wda_click, args=(capabilities, appiumurl, bundle_id, out_dir, country,))
        wdaclickprocess.start()

        # 等待 150 秒ß
        time.sleep(150)

        # 终止 wdaclickprocess
        if wdaclickprocess.is_alive():
            wdaclickprocess.terminate()
            wdaclickprocess.join()
            
        # if wda_process.poll() is None:  # WDA 进程仍在运行
        #     wda_process.terminate()
        #     wda_process.wait()

        # 卸载应用逻辑
        uninstall_cmd = f"ideviceinstaller -u {UDID} -U {bundle_id}"
        subprocess.run(uninstall_cmd, shell=True, check=True)
    except Exception as e:
        print(f"An error occurred: {e}")
    
    # 卸载应用提取信息
    uninstallcmd = f"ideviceinstaller -u {UDID} -U {bundle_id}"
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

# def run_wda(wdacommand, wda_process, working_directory):
#     """
#     运行 WebDriverAgent 服务，并监控其状态。
#     :param wdacommand: WebDriverAgent 的命令
#     :param wda_process: 当前运行的 WDA 进程
#     :param working_directory: WebDriverAgent 的工作目录
#     """
#     try:
#         while True:
#             retcode = wda_process.poll()
#             if retcode is not None:
#                 print(f"WDA process exited with code {retcode}, restarting...")
#                 wda_process = subprocess.Popen(wdacommand, cwd=working_directory)
#             else:
#                 # WDA 正常运行
#                 time.sleep(30)
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         if wda_process:
#             wda_process.terminate()
            
def wda_click(capabilities,appiumurl,bundleId,out_dir,country):
    try:
        appium_options = AppiumOptions()
        appium_options.load_capabilities(capabilities)
        driver = webdriver.Remote(appiumurl, options=appium_options)

        end_time = time.time() + 120
        clicked_elements = []
        timestamps = []

        try:
            while time.time() < end_time:
                # 保持应用在前台
                driver.activate_app(bundleId)
                while find_and_click_agree(driver,clicked_elements,country):
                    time.sleep(5)
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
                time.sleep(5)
        except Exception as e:
            print(e)
        driver.quit()

    except Exception as e:
        print("appium failed : {e}")
        
def find_and_click_agree(driver,clicked_elements,country):
    try:
        if country == 'cn':
        # 查找所有包含 "同意" 字样且不包含 "不同意" 字样的元素
            agree_elements = driver.find_elements(
                AppiumBy.XPATH,
                "//*[(contains(@text, '同意') or contains(@text, '继续') or contains(@text, '取消') or contains(@text, '以后') or contains(@text, '允许') or contains(@text, '确定') or contains(@text, '好') or contains(@text, '无线局域网与蜂窝网络')) and not(contains(@text, '不'))]"
                " | //*[(contains(@name, '同意')  or contains(@name, '继续') or contains(@name, '取消') or contains(@name, '以后') or contains(@name, '允许') or contains(@name, '确定') or contains(@name, '好') or contains(@name, '无线局域网与蜂窝网络')) and not(contains(@name, '不'))]"
                " | //*[(contains(@label, '同意') or contains(@label, '继续') or contains(@label, '取消') or contains(@label, '以后') or contains(@label, '允许') or contains(@label, '确定') or contains(@label, '好') or contains(@label, '无线局域网与蜂窝网络')) and not(contains(@label, '不'))]"
            )
        elif country == 'us':
            # 查找所有包含 "agree" 字样且不包含 "NO" 字样的元素
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
